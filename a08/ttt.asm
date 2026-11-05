; Native 8008 port of https://github.com/davidly/cpm_compilers/blob/main/asm/TTT.ASM.
; Same ascending-move alpha-beta minimax, first moves 0, 1, 4.
; Every root must score 5 (tie); one iteration visits 6493 nodes.
; Recursion is replaced by nine explicit 16-byte RAM frames. The 8008's
; hardware address stack is used only for short, nonrecursive helpers.
; B = frame offset (00H..80H), C = returned score, D = node count low byte.
; E holds the move's board address until WINNER.
; Offset bit 4 is depth parity; offsets 40H/80H are depths 4/8.
; Even depths minimize (O to move); odd depths maximize (X to move).
; Separate MIN and MAX copies of the search know the parity statically.
; Frame fields: last tried board address, value, alpha, beta.
; A MIN frame's alpha and a MAX frame's beta cannot change during its
; life, so it reads them from the parent's frame instead of copying them.
; The root's parent is offset 0F0H, holding the minimum score as alpha.
; The board, its zero sentinel and the node counter share the frames page,
; so H stays at FRAMES throughout the search except inside WINNER.
; A parent's last tried move is the move its child must undo.
; No CP/M command tail: change LOOPS to configure benchmark iterations.
LOOPS   EQU 1
FRAMES  EQU 1000H
BOARD   EQU FRAMES+0A0H        ; nine cells, then a zero sentinel
COUNTHI EQU FRAMES+0E0H        ; moves high byte; D holds the low byte
ROOTUP  EQU FRAMES+0F0H        ; the root's virtual MAX parent
VARS    EQU 1200H              ; first move, iterations low/high
WINPROCS EQU 1300H             ; line checks; entry points within one page
WINPAGE EQU 1400H              ; WINNER and its LOW entry table
        ORG 0040H
        LHI HIGH VARS
        LLI 1
        LMI 0
        INL
        LMI 0
AGAIN:  LHI HIGH BOARD
        LLI LOW BOARD
        LCI 10D
CLEAR:  LMI 0
        INL
        DCC
        JFZ CLEAR
        LLI LOW COUNTHI
        LMI 0
        LLI LOW ROOTUP+2
        LMI 2                  ; root alpha = minimum score
        LDI 0
        LHI HIGH VARS
        LLI 0
        LMI 0
ROOT:   LHI HIGH VARS
        LLI 0
        LAM                    ; first move: 0, then 1, then 4
        ADI LOW BOARD
        LEA
        LHI HIGH FRAMES
        LLE
        LMI 1
        LBI 0
        LLI 3
        LMI 9D                 ; beta = maximum score
        JMP ENTERMIN           ; O minimizes after X's first move

; ENTERMIN/ENTERMAX: B is the new frame, E its last move, H = FRAMES.
ENTERMIN:
        IND                    ; count every minimax invocation
        CTZ COUNTUP
        LAB
        CPI 40H
        JTC INITMIN
        CAL WINNER
        LCI 6                  ; X just moved and won
        JTZ RETMIN
        LAB
        CPI 80H
        LCI 5
        JTZ RETMIN
INITMIN:
        LLB
        LMI LOW BOARD-1        ; scanning starts at cell zero
        INL
        LMI 9D                 ; minimum starts with the maximum possible value
NEXTMIN:
        LLB
        LLM                    ; last tried cell
        XRA                    ; CPM finds an empty (zero) cell
SCANMIN:
        INL
        CPM
        JFZ SCANMIN
        LAL
        CPI LOW BOARD+9D
        JTZ EXHMIN             ; reached the sentinel
        LMI 2                  ; O moves
        LEL
        LLB
        LME                    ; parent resumes after this cell
        LAB
        SUI 0EH
        LLA
        LCM                    ; this MIN frame's alpha, from its parent
        ADI 20H
        LLA
        LMC                    ; child alpha
        LAB
        ADI 10H
        LBA
ENTERMAX:
        IND
        CTZ COUNTUP
        LAB
        CPI 40H
        JTC INITMAX
        CAL WINNER
        LCI 4                  ; O just moved and won
        JTZ RETMAX
INITMAX:
        LLB
        LMI LOW BOARD-1
        INL
        LMI 2                  ; maximum starts with the minimum possible value
NEXTMAX:
        LLB
        LLM
        XRA
SCANMAX:
        INL
        CPM
        JFZ SCANMAX
        LAL
        CPI LOW BOARD+9D
        JTZ EXHMAX
        LMI 1                  ; X moves
        LEL
        LLB
        LME
        LAB
        SUI 0DH
        LLA
        LCM                    ; this MAX frame's beta, from its parent
        ADI 20H
        LLA
        LMC                    ; child beta
        LAB
        ADI 10H
        LBA
        JMP ENTERMIN

EXHMIN: LLB
        INL
        LCM                    ; no more moves: return the accumulated value
; RETMIN returns C from a MIN frame to its MAX parent (or to the root).
RETMIN: LAB
        SUI 10H
        JTC ROOTDONE
        LBA                    ; resume the parent
        LLA
        LLM                    ; the parent's move led to this child
        LMI 0                  ; undo it
        LAC
        CPI 6                  ; cannot do better than a win
        JTZ RETMAX
        LLB
        INL                    ; parent value
        CPM
        JTC NEXTMAX
        JTZ NEXTMAX
        LMC
        INL                    ; alpha
        CPM
        JTC MAXBETA
        JTZ MAXBETA
        LMC                    ; alpha = score (dead if beta prunes)
MAXBETA:
        LAB
        SUI 0DH
        LLA                    ; beta, from the MIN parent
        LAC
        CPM
        JFC RETMAX             ; score >= beta: prune
        JMP NEXTMAX

EXHMAX: LLB
        INL
        LCM
; RETMAX returns C from a MAX frame (never the root) to its MIN parent.
RETMAX: LAB
        SUI 10H
        LBA
        LLA
        LLM
        LMI 0
        LAC
        CPI 4                  ; cannot do worse than a loss
        JTZ RETMIN
        LLB
        INL                    ; parent value
        CPM
        JFC NEXTMIN            ; score >= value, so no improvement
        LMC
        INL
        INL                    ; beta
        CPM
        JFC MINALPHA
        LMC                    ; beta = score (dead if alpha prunes)
MINALPHA:
        LAB
        SUI 0EH
        LLA                    ; alpha, from the MAX parent
        LAC
        CPM
        JTC RETMIN             ; score < alpha: prune
        JTZ RETMIN             ; score == alpha: prune
        JMP NEXTMIN

; COUNTUP carries the node count into its high byte. H = FRAMES.
COUNTUP:
        LLI LOW COUNTHI
        LAM
        ADI 1
        LMA
        RET

ROOTDONE:
        LAC
        CPI 5
        JFZ FAIL               ; a perfect opponent must force a tie
        LHI HIGH VARS
        LLI 0
        LAM
        LEA
        ADI LOW BOARD
        LHI HIGH BOARD
        LLA
        LMI 0
        LHI HIGH VARS
        LLI 0
        LAE
        CPI 4
        JTZ ITERDONE
        NDA
        LAI 1
        JTZ SETROOT
        LAI 4
SETROOT:
        LMA
        JMP ROOT
ITERDONE:
        LLI 1
        LAM
        ADI 1
        LMA
        LEA
        INL
        LAM
        ACI 0
        LMA
        CPI HIGH LOOPS
        JFZ AGAIN
        LAE
        CPI LOW LOOPS
        JFZ AGAIN
        LHI HIGH MOVEMSG
        LLI LOW MOVEMSG
        CAL PRINT
        LED
        LHI HIGH COUNTHI
        LLI LOW COUNTHI
        LDM
        CAL PUTU
        LHI HIGH ITERMSG
        LLI LOW ITERMSG
        CAL PRINT
        LDI HIGH LOOPS
        LEI LOW LOOPS
        CAL PUTU
        LAI 012
        OUT 12
        HLT
FAIL:   LHI HIGH FAILMSG
        LLI LOW FAILMSG
        CAL PRINT
        HLT

MOVEMSG: DATA "moves: ", 0
ITERMSG: DATA 012, "iterations: ", 0
FAILMSG: DATA "FAIL: minimax did not tie", 012, 0

; Console helpers: OUT octal 12 replaces CP/M BDOS output.
; PRINT prints a zero-terminated string at HL, clobbering A and HL.
PRINT:  LAM
        NDA
        RTZ
        OUT 12
        INL
        JFZ PRINT
        INH
        JMP PRINT

; PUTU prints unsigned DE in decimal, clobbering all registers.
; BC is a decimal divisor, H counts subtractions, L suppresses leading zeros.
; Maximum hardware call depth, including the caller, is two.
PUTU:   LLI 0
        LBI HIGH 10000D
        LCI LOW 10000D
        CAL PDIGIT
        LBI HIGH 1000D
        LCI LOW 1000D
        CAL PDIGIT
        LBI 0
        LCI 100D
        CAL PDIGIT
        LCI 10D
        CAL PDIGIT
        LCI 1
        LLI 1                  ; always print the units digit, including zero
        CAL PDIGIT
        RET
PDIGIT: LHI 0
PDIV:   LAE
        SUC
        LEA
        LAD
        SBB
        LDA
        JTC PRESTORE
        INH
        JMP PDIV
PRESTORE:
        LAE
        ADC
        LEA
        LAD
        ACB
        LDA
        LAH
        NDA
        JFZ PSHOW
        LAL
        NDA
        RTZ
PSHOW:  LAH
        ADI '0'
        OUT 12
        LLI 1
        RET

; WINNER checks only lines through the last move, as in the 8080 source.
; E supplies the last move's board address and is preserved, as are B, C, D.
; Returns Z when the piece on that cell completes a line (A = piece), else NZ.
; The 8008 has no indirect jump. All entry points share one page, so only
; the LOW byte of a RAM trampoline is patched; its RET uses WINNER's
; existing hardware return slot.
        ORG WINPROCS
W0P0:   LLI LOW BOARD+1D
        CPM
        JFZ W0P1
        INL
        CPM
        RTZ
W0P1:   LLI LOW BOARD+3D
        CPM
        JFZ W0P2
        LLI LOW BOARD+6D
        CPM
        RTZ
W0P2:   LLI LOW BOARD+4D
        CPM
        RFZ
        LLI LOW BOARD+8D
        CPM
        RET

W1P0:   LLI LOW BOARD+0D
        CPM
        JFZ W1P1
        LLI LOW BOARD+2D
        CPM
        RTZ
W1P1:   LLI LOW BOARD+4D
        CPM
        RFZ
        LLI LOW BOARD+7D
        CPM
        RET

W2P0:   LLI LOW BOARD+0D
        CPM
        JFZ W2P1
        INL
        CPM
        RTZ
W2P1:   LLI LOW BOARD+5D
        CPM
        JFZ W2P2
        LLI LOW BOARD+8D
        CPM
        RTZ
W2P2:   LLI LOW BOARD+4D
        CPM
        RFZ
        LLI LOW BOARD+6D
        CPM
        RET

W3P0:   LLI LOW BOARD+0D
        CPM
        JFZ W3P1
        LLI LOW BOARD+6D
        CPM
        RTZ
W3P1:   LLI LOW BOARD+4D
        CPM
        RFZ
        INL
        CPM
        RET

W4P0:   LLI LOW BOARD+0D
        CPM
        JFZ W4P1
        LLI LOW BOARD+8D
        CPM
        RTZ
W4P1:   LLI LOW BOARD+2D
        CPM
        JFZ W4P2
        LLI LOW BOARD+6D
        CPM
        RTZ
W4P2:   LLI LOW BOARD+1D
        CPM
        JFZ W4P3
        LLI LOW BOARD+7D
        CPM
        RTZ
W4P3:   LLI LOW BOARD+3D
        CPM
        RFZ
        LLI LOW BOARD+5D
        CPM
        RET

W5P0:   LLI LOW BOARD+3D
        CPM
        JFZ W5P1
        INL
        CPM
        RTZ
W5P1:   LLI LOW BOARD+2D
        CPM
        RFZ
        LLI LOW BOARD+8D
        CPM
        RET

W6P0:   LLI LOW BOARD+4D
        CPM
        JFZ W6P1
        LLI LOW BOARD+2D
        CPM
        RTZ
W6P1:   LLI LOW BOARD+0D
        CPM
        JFZ W6P2
        LLI LOW BOARD+3D
        CPM
        RTZ
W6P2:   LLI LOW BOARD+7D
        CPM
        RFZ
        INL
        CPM
        RET

W7P0:   LLI LOW BOARD+1D
        CPM
        JFZ W7P1
        LLI LOW BOARD+4D
        CPM
        RTZ
W7P1:   LLI LOW BOARD+6D
        CPM
        RFZ
        LLI LOW BOARD+8D
        CPM
        RET

W8P0:   LLI LOW BOARD+0D
        CPM
        JFZ W8P1
        LLI LOW BOARD+4D
        CPM
        RTZ
W8P1:   LLI LOW BOARD+2D
        CPM
        JFZ W8P2
        LLI LOW BOARD+5D
        CPM
        RTZ
W8P2:   LLI LOW BOARD+6D
        CPM
        RFZ
        INL
        CPM
        RET

        ORG WINPAGE
WINNER: LHI HIGH WINLOW
        LLE                    ; WINLOW is indexed by the board address
        LAM
        LLI LOW WJUMP+1
        LMA
        LHI HIGH BOARD
        LLE
        LAM                    ; piece placed by that move (always nonzero)
WJUMP:  JMP W0P0               ; LOW byte patched above; full RAM is available
        ORG WINPAGE+LOW BOARD
WINLOW: DATA LOW W0P0, LOW W1P0, LOW W2P0, LOW W3P0, LOW W4P0
        DATA LOW W5P0, LOW W6P0, LOW W7P0, LOW W8P0
        END
