; Native 8008 port of https://github.com/davidly/cpm_compilers/blob/main/asm/TTT.ASM.
; Same ascending-move alpha-beta minimax, first moves 0, 1, 4.
; Every root must score 5 (tie); one iteration visits 6493 nodes.
; Recursion is replaced by nine explicit 16-byte RAM frames. The 8008's
; hardware address stack is used only for short, nonrecursive helpers.
; B = frame offset (00H..80H), C = returned score, D = scratch.
; E holds the candidate/last move until WINNER, which may clobber it.
; Offset bit 4 is depth parity; offsets 40H/80H are depths 4/8.
; Frame fields: next move, value, alpha, beta, last move, current player.
; Even depths minimize (O to move); odd depths maximize (X to move).
; No CP/M command tail: change LOOPS to configure benchmark iterations.
LOOPS   EQU 1
FRAMES  EQU 1000H
BOARD   EQU 1100H
VARS    EQU 1200H              ; moves low/high, first move, iterations low/high
WINPROCS EQU 1300H             ; nine three-byte JMP slots, within one page
        ORG 0040H
        LHI HIGH VARS
        LLI 3
        LMI 0
        INL
        LMI 0
AGAIN:  LHI HIGH BOARD
        LLI 0
        LCI 9D
CLEAR:  LMI 0
        INL
        DCC
        JFZ CLEAR
        LHI HIGH VARS
        LLI 0
        LMI 0
        INL
        LMI 0
        INL
        LMI 0
ROOT:   LHI HIGH VARS
        LLI 2
        LEM                    ; first move: 0, then 1, then 4
        LHI HIGH BOARD
        LLE
        LMI 1
        LBI 0
        LLB
        LHI HIGH FRAMES
        INL
        INL
        LMI 2                  ; alpha = minimum score
        INL
        LMI 9D                 ; beta = maximum score
        INL
        LME                    ; remember the root's first move
        INL
        LMI 2                  ; O minimizes after X's first move
ENTER:  LHI HIGH VARS
        LLI 0
        LAM
        ADI 1
        LMA
        JFC COUNTED            ; update the high byte only on low-byte carry
        INL
        LAM
        ACI 0
        LMA                    ; count every minimax invocation
COUNTED:
        LAB
        CPI 40H
        JTC INITFRAME
        CAL WINNER             ; E survived frame setup and node counting
        LAC
        NDA
        JTZ NOWIN
        CPI 1
        LCI 6                  ; X wins
        JTZ RETURN
        LCI 4                  ; O wins
        JMP RETURN
NOWIN:  LAB
        CPI 80H
        LCI 5
        JTZ RETURN
INITFRAME:
        LLB
        LHI HIGH FRAMES
        LMI 0                  ; ascending move order, starting at cell zero
        INL
        LAB
        NDI 10H
        LAI 9D                 ; minimum starts with the maximum possible value
        JTZ SETVALUE
        LAI 2                  ; maximum starts with the minimum possible value
SETVALUE:
        LMA
NEXTMOVE:
        LLB
        LHI HIGH FRAMES
        LEM                    ; restore the next candidate once
        LHI HIGH BOARD
SCANMOVE:
        LAE
        CPI 9D
        JTZ EXHAUSTED
        LLE
        LAM
        NDA
        JTZ FOUND
        INE
        JMP SCANMOVE
FOUND:
        LLB
        LHI HIGH FRAMES
        LAE
        ADI 1
        LMA                    ; save resume position only before descent
        ; HL still addresses the parent; get player and inherited bounds.
        INL
        INL
        LCM                    ; inherited alpha
        INL
        LDM                    ; inherited beta
        INL
        INL
        LAM                    ; parent's current player
        LHI HIGH BOARD
        LLE
        LMA                    ; make this move
        LAB
        ADI 10H
        LBA
        LLB
        LHI HIGH FRAMES
        INL
        INL
        LMC                    ; child alpha
        INL
        LMD                    ; child beta
        INL
        LME                    ; remember where to undo this move
        INL
        LAB
        NDI 10H
        LAI 2
        JTZ CHILDPLAYER
        LAI 1
CHILDPLAYER:
        LMA                    ; child player
        JMP ENTER
EXHAUSTED:
        LLB
        LHI HIGH FRAMES
        INL
        LCM                    ; no more moves: return the accumulated value
RETURN: LAB
        NDA
        JTZ ROOTDONE
        LLB
        LHI HIGH FRAMES
        INL
        INL
        INL
        INL
        LEM                    ; child's last move
        LHI HIGH BOARD
        LLE
        LMI 0                  ; undo it
        LAB
        SUI 10H
        LBA                    ; resume its parent
        LAB
        NDI 10H
        JFZ MAXRETURN
MINRETURN:
        LAC
        CPI 4                  ; cannot do worse than a loss
        JTZ RETURN
        LLB
        LHI HIGH FRAMES
        INL                    ; parent value
        LAC
        CPM
        JFC NEXTMOVE           ; score >= value, so no improvement
        LMC
        INL                    ; alpha
        CPM
        JTC RETURN             ; score < alpha: prune
        JTZ RETURN             ; score == alpha: prune
        INL                    ; beta
        CPM
        JFC NEXTMOVE
        LMC                    ; beta = score
        JMP NEXTMOVE
MAXRETURN:
        LAC
        CPI 6                  ; cannot do better than a win
        JTZ RETURN
        LLB
        LHI HIGH FRAMES
        INL                    ; parent value
        LAC
        CPM
        JTC NEXTMOVE
        JTZ NEXTMOVE
        LMC
        INL
        INL                    ; beta
        CPM
        JFC RETURN             ; score >= beta: prune
        DCL                    ; alpha
        CPM
        JTC NEXTMOVE
        JTZ NEXTMOVE
        LMC                    ; alpha = score
        JMP NEXTMOVE
ROOTDONE:
        LAC
        CPI 5
        JFZ FAIL               ; a perfect opponent must force a tie
        LHI HIGH VARS
        LLI 2
        LAM
        LEA
        LHI HIGH BOARD
        LLE
        LMI 0
        LHI HIGH VARS
        LLI 2
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
        LLI 3
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
        LHI HIGH VARS
        LLI 0
        LEM
        INL
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

; WINNER checks only lines through the last move, as in the 8080 source.
; E supplies the last move (0..8); B is preserved.
; C returns the winning piece or zero. D/E/HL/A are scratch.
; The 8008 has no indirect jump. Copy the selected JMP's two address bytes
; into a RAM trampoline; its RET uses WINNER's existing hardware return slot.
WINNER: LHI HIGH BOARD      ; E already holds the most recent move
        LLE
        LCM                    ; piece placed by that move (always nonzero)
        LAE
        ADE
        ADE                    ; three bytes per jump-table entry
        LLA
        LHI HIGH WINPROCS
        INL                    ; skip the JMP opcode
        LDM                    ; target low byte
        INL
        LEM                    ; target high byte
        LHI HIGH WJUMP
        LLI LOW WJUMP+1
        LMD
        INL
        LME
        LHI HIGH BOARD
        LAC                    ; compare the last piece against each pair
WJUMP:  JMP 0                  ; patched above; full RAM is available

W0P0:  LLI 1D
        CPM
        JFZ W0P1
        INL
        CPM
        RTZ
W0P1:  LLI 3D
        CPM
        JFZ W0P2
        LLI 6D
        CPM
        RTZ
W0P2:  LLI 4D
        CPM
        JFZ WNONE
        LLI 8D
        CPM
        RTZ
        JMP WNONE

W1P0:  LLI 0D
        CPM
        JFZ W1P1
        LLI 2D
        CPM
        RTZ
W1P1:  LLI 4D
        CPM
        JFZ WNONE
        LLI 7D
        CPM
        RTZ
        JMP WNONE

W2P0:  LLI 0D
        CPM
        JFZ W2P1
        INL
        CPM
        RTZ
W2P1:  LLI 5D
        CPM
        JFZ W2P2
        LLI 8D
        CPM
        RTZ
W2P2:  LLI 4D
        CPM
        JFZ WNONE
        LLI 6D
        CPM
        RTZ
        JMP WNONE

W3P0:  LLI 0D
        CPM
        JFZ W3P1
        LLI 6D
        CPM
        RTZ
W3P1:  LLI 4D
        CPM
        JFZ WNONE
        INL
        CPM
        RTZ
        JMP WNONE

W4P0:  LLI 0D
        CPM
        JFZ W4P1
        LLI 8D
        CPM
        RTZ
W4P1:  LLI 2D
        CPM
        JFZ W4P2
        LLI 6D
        CPM
        RTZ
W4P2:  LLI 1D
        CPM
        JFZ W4P3
        LLI 7D
        CPM
        RTZ
W4P3:  LLI 3D
        CPM
        JFZ WNONE
        LLI 5D
        CPM
        RTZ
        JMP WNONE

W5P0:  LLI 3D
        CPM
        JFZ W5P1
        INL
        CPM
        RTZ
W5P1:  LLI 2D
        CPM
        JFZ WNONE
        LLI 8D
        CPM
        RTZ
        JMP WNONE

W6P0:  LLI 4D
        CPM
        JFZ W6P1
        LLI 2D
        CPM
        RTZ
W6P1:  LLI 0D
        CPM
        JFZ W6P2
        LLI 3D
        CPM
        RTZ
W6P2:  LLI 7D
        CPM
        JFZ WNONE
        INL
        CPM
        RTZ
        JMP WNONE

W7P0:  LLI 1D
        CPM
        JFZ W7P1
        LLI 4D
        CPM
        RTZ
W7P1:  LLI 6D
        CPM
        JFZ WNONE
        LLI 8D
        CPM
        RTZ
        JMP WNONE

W8P0:  LLI 0D
        CPM
        JFZ W8P1
        LLI 4D
        CPM
        RTZ
W8P1:  LLI 2D
        CPM
        JFZ W8P2
        LLI 5D
        CPM
        RTZ
W8P2:  LLI 6D
        CPM
        JFZ WNONE
        INL
        CPM
        RTZ
        JMP WNONE

WNONE:  LCI 0
        RET
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

        ORG WINPROCS
        JMP W0P0
        JMP W1P0
        JMP W2P0
        JMP W3P0
        JMP W4P0
        JMP W5P0
        JMP W6P0
        JMP W7P0
        JMP W8P0
        END
