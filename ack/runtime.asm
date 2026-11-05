; ACK EM support for the 8008. AB is a 16-bit value (A low, B high).
; C functions use the RAM stack; CAL/RET are only used by short helpers.
RSP EQU 3F00H
FP EQU RSP+2
RV EQU RSP+4
PT EQU RSP+6
OT EQU RSP+8D
X EQU RSP+10D
Q EQU RSP+12D
REM EQU RSP+14D
SIGNQ EQU RSP+16D
SIGNR EQU RSP+17D
        ORG 0040H
        LHI HIGH RSP
        LLI LOW RSP
        LMI 0
        INL
        LMI 3FH
        LAI LOW STOP
        LBI HIGH STOP
        CAL PUSH
        JMP F_MAIN
STOP:   HLT
; LOADSP leaves AB/CD intact and returns HL = RSP.
LOADSP: LHI HIGH RSP
        LLI LOW RSP
        LEM
        INL
        LHM
        LLE
        RET
; ADDSP adds signed AB to RSP, returning HL = the updated pointer.
; C/D are preserved, E is scratch. Every stack slot is word aligned.
ADDSP:  LHI HIGH RSP
        LLI LOW RSP
        ADM
        LMA
        LEA
        INL
        LAB
        ACM
        LMA
        LHA
        LLE
        CPI HIGH STACKMIN
        JTC STACKFAULT
        RET
; PUSH/POP preserve C/D and use ACK's word-aligned stack.
; Only update the pointer high byte on a borrow/carry; loads preserve carry.
; Keep the PUSH bounds check on both paths, including the no-borrow path.
; Copy the old pointer low byte to E instead of reading it from RAM twice.
PUSH:   LEA
        LHI HIGH RSP
        LLI LOW RSP
        LAM
        SUI 2
        LMA
        INL
        LAM
        JFC PUSHREADY
        SBI 0
        LMA
PUSHREADY:
        CPI HIGH STACKMIN
        JTC STACKFAULT
        DCL
        LLM
        LHA
        LAE
        LMA
        INL
        LMB
        RET
POP:    LHI HIGH RSP
        LLI LOW RSP
        LAM
        LEA
        ADI 2
        LMA
        INL
        LBM
        JFC POPREADY
        INB
        LMB
        DCB
POPREADY:
        LHB
        LLE
        LAM
        INL
        LBM
        RET
LOCAL:  LHI HIGH FP
        LLI LOW FP
        ADM
        LEA
        INL
        LAB
        ACM
        LHA
        LLE
        RET
; ACK frames are word aligned. ENTER preserves CD and checks the stack floor.
ENTER:  LHI HIGH FP
        LLI LOW FP
        LEM
        INL
        LBM
        LLI LOW RSP
        LAM
        SUI 2
        LMA
        INL
        LAM
        SBI 0
        LMA
        CPI HIGH STACKMIN
        JTC STACKFAULT
        DCL
        LLM
        LHA
        LME
        INL
        LMB
        DCL
        LAL
        LBH
        LHI HIGH FP
        LLI LOW FP
        LMA
        INL
        LMB
        RET
; The saved FP and return word are adjacent at FP. Release them together,
; then read both directly instead of calling the general POP twice.
; Software calls may clobber CD; the function result remains in RV.
LEAVEVALUE: LHI HIGH RV
        LLI LOW RV
        LMA
        INL
        LMB
LEAVE:  LHI HIGH FP
        LLI LOW FP
        LAM
        ADI 4
        LCA
        INL
        LAM
        ACI 0
        LBA
        LLI LOW RSP
        LMC
        INL
        LMB
        LLI LOW FP
        LEM
        INL
        LHM
        LLE
        LAM
        LCA
        INL
        LAM
        LDA
        INL
        JFZ LEAVERET
        INH
LEAVERET:
        LAM
        LBA
        INL
        LAM
        LEA
        LHI HIGH FP
        LLI LOW FP
        LMC
        INL
        LMD
        LHI HIGH RETURNJ
        LLI LOW RETURNJ+1
        LMB
        INL
        LME
RETURNJ: JMP 0
LD1:
        LHB
        LLA
        LAM
        LBI 0
        RET
LD2:
        LHB
        LLA
        LAM
        INL
        LBM
        RET
ST1:
        LCA
        LDB
        CAL POP
        LHD
        LLC
        LMA
        RET
ST2:
        LCA
        LDB
        CAL POP
        LHD
        LLC
        LMA
        INL
        LMB
        RET
DUP2:   CAL LOADSP
        LAM
        INL
        LBM
        RET
; Expression helpers take their top operand in AB and return results in AB.
; Stores pop their value from RAM and produce no expression result.
; DUP2 reads the existing RAM top without consuming it.
; Unary arithmetic, logical and byte-conversion operations.
NEG:    LEA
        LAB
        XRI 0FFH
        LBA
        LAE
        XRI 0FFH
        ADI 1
        LEA
        LAB
        ACI 0
        LBA
        LAE
        RET
NEGI:   JMP NEG
COM:
        XRI 0FFH
        LEA
        LAB
        XRI 0FFH
        LBA
        LAE
        RET
SX1:
        LBI 0
        NDA
        JFS SXDONE
        LBI 0FFH
SXDONE: RET
ZX1:
        LBI 0
        RET
; Binary helpers take the right operand in AB and pop the left operand.
; Results remain in AB, avoiding right-operand and result stack round trips.
; Multiplication is modulo 65536. CD is the unsigned repeat count.
MUL:
        LCA
        LDB
        CAL POP
        LHI HIGH X
        LLI LOW X
        LMA
        INL
        LMB
        LAI 0
        LBI 0
MULLOOP:
        LEA
        LAC
        ORD
        JTZ MULDONE
        LAC
        NDA
        JFZ MULDEC
        DCD
MULDEC: DCC
        LAE
        LHI HIGH X
        LLI LOW X
        ADM
        LEA
        INL
        LAB
        ACM
        LBA
        LAE
        JMP MULLOOP
MULDONE:
        LAE
        RET
; Raw division: AB dividend, CD divisor; returns AB quotient and REM.
; HL counts the quotient. C/D, E and HL are clobbered.
DIVIDE: LEA
        LAC
        ORD
        JTZ DIVZERO
        LAE
        LHI 0
        LLI 0
DIVLOOP:
        SUC
        LEA                    ; low byte of the trial difference
        LAB
        SBD
        JTC DIVDONE
        LBA
        LAE
        INL
        JFZ DIVLOOP
        INH
        JMP DIVLOOP
DIVDONE:
        LAE
        ADC                    ; undo the failed low-byte subtraction
        LEA                    ; B still holds the remainder's high byte
        LCL
        LDH
        LHI HIGH REM
        LLI LOW REM
        LME
        INL
        LMB
        LAC
        LBD
        RET
UDIV:
        LCA
        LDB
        CAL POP
        CAL DIVIDE
        RET
SDIV:   LHI HIGH SIGNQ
        LLI LOW SIGNQ
        LMI 0
        INL
        LMI 0
        LEA
        LAB
        NDA
        JFS SDIVPOS
        LAE
        CAL NEG
        LHI HIGH SIGNQ
        LLI LOW SIGNQ
        LMI 1
        LEA
SDIVPOS:
        LAE
        LCA
        LDB
        CAL POP
        LEA
        LAB
        NDA
        JFS SDIVLEFT
        LAE
        CAL NEG
        LEA
        LHI HIGH SIGNQ
        LLI LOW SIGNQ
        LAM
        XRI 1
        LMA
        INL
        LMI 1
SDIVLEFT:
        LAE
        CAL DIVIDE
        RET
DIVU:   CAL UDIV
        RET
MODU:   CAL UDIV
        LHI HIGH REM
        LLI LOW REM
        LAM
        INL
        LBM
        RET
DIVI:   CAL SDIV
        LEA
        LHI HIGH SIGNQ
        LLI LOW SIGNQ
        LAM
        NDA
        LAE
        RTZ
        CAL NEG
        RET
MODI:   CAL SDIV
MODRESULT:
        LHI HIGH SIGNR
        LLI LOW SIGNR
        LAM
        LCA
        LLI LOW REM
        LAM
        INL
        LBM
        LEA
        LAC
        NDA
        LAE
        RTZ
        CAL NEG
        RET
; Comparison returns -1, zero, or +1 in AB, using the binary helper ABI.
CMI:
        LCA
        LAB
        XRI 80H
        LDA
        CAL POP
        LEA
        LAB
        XRI 80H
        JMP CMPHI
CMU:
        LCA
        LDB
        CAL POP
        LEA
        LAB
CMPHI:  CPD
        JTC CMPLESS
        JFZ CMPMORE
        LAE
        CPC
        JTC CMPLESS
        JFZ CMPMORE
        LAI 0
        LBI 0
        RET
CMPLESS:
        LAI 0FFH
        LBI 0FFH
        RET
CMPMORE:
        LAI 1
        LBI 0
        RET
; Native console leaf functions follow the same RAM frame convention as C.
F_PUTCHAR:
        CAL ENTER
        LAI 4
        LBI 0
        CAL LOCAL
        LAM
        INL
        LBM
        LHI HIGH RV
        LLI LOW RV
        LMA
        INL
        LMB
        CAL PRINTCHAR
        JMP LEAVE
PRINTCHAR:
        CPI 10D
        JFZ PRINTBYTE
        LAI 13D
PRINTBYTE:
        OUT 12
        RET
F_GETCHAR:
        CAL ENTER
        INP 2
        NDI 7FH
        CPI 13D
        JFZ GOTCHAR
        LAI 10D
GOTCHAR:
        LHI HIGH RV
        LLI LOW RV
        LMA
        INL
        LMI 0
        JMP LEAVE
F_PUTS:
        CAL ENTER
        LAI 4
        LBI 0
        CAL LOCAL
        LAM
        INL
        LHM
        LLA
PUTSLOOP:
        LAM
        NDA
        JTZ PUTSDONE
        CAL PRINTCHAR
        INL
        JFZ PUTSLOOP
        INH
        JMP PUTSLOOP
PUTSDONE:
        LAI 13D
        OUT 12
        LHI HIGH RV
        LLI LOW RV
        LMI 0
        INL
        LMI 0
        JMP LEAVE
STACKFAULT:
        LHI HIGH STACKMSG
        LLI LOW STACKMSG
        JMP TRAPMSG
DIVZERO:
        LHI HIGH DIVMSG
        LLI LOW DIVMSG
TRAPMSG:
        LAM
        NDA
        JTZ TRAPHALT
        OUT 12
        INL
        JFZ TRAPMSG
        INH
        JMP TRAPMSG
TRAPHALT:
        HLT
STACKMSG: DB "ACK stack overflow",13D,0
DIVMSG: DB "ACK division by zero",13D,0
; Dense C switch: descriptor is default, minimum, range, case addresses.
TAB EQU RSP+24D
CSA:    CAL POP
        LHI HIGH TAB
        LLI LOW TAB
        LMA
        INL
        LMB
        CAL POP
        CAL LOADTAB
        INL
        INL
        JFZ CSAMIN
        INH
CSAMIN:
        SUM
        LEA
        INL
        LAB
        SBM
        LBA
        INL
        JFZ CSARANGE
        INH
CSARANGE:
        LCM
        INL
        LDM
        CPD
        JTC CSAIN
        JFZ CSAOUT
        LAE
        CPC
        JTC CSAIN
        JTZ CSAIN
CSAOUT: CAL LOADTAB
        JMP CSATARGET
CSAIN:  LAE
        ADA
        LEA
        LAB
        RAL
        LBA
        LAE
        ADI 6
        LEA
        LAB
        ACI 0
        LBA
        LAE
        LHI HIGH TAB
        LLI LOW TAB
        ADM
        LEA
        INL
        LAB
        ACM
        LHA
        LLE
CSATARGET:
        LAM
        INL
        LBM
JUMPAB: LHI HIGH INDIRECT
        LLI LOW INDIRECT+1
        LMA
        INL
        LMB
INDIRECT:
        JMP 0
LOADTAB:
        LHI HIGH TAB
        LLI LOW TAB
        LEM
        INL
        LHM
        LLE
        RET

; Private quotient scratch. Reuse never crosses a call or control-flow edge.
DQUOT EQU RSP+32D
SAVEQUOT:
        LHI HIGH DQUOT
        LLI LOW DQUOT
        LMA
        INL
        LMB
        RET
RMUSAVE:
        CAL UDIV
        CAL SAVEQUOT
        LHI HIGH REM
        LLI LOW REM
        LAM
        INL
        LBM
        RET
RMISAVE:
        CAL DIVI
        CAL SAVEQUOT
        JMP MODRESULT
