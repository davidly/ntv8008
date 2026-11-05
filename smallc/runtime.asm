; SmallC-85 support for the 8008. AB is a 16-bit value (A low, B high).
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
SADDR EQU RSP+18D             ; indirect-store address saved off the RAM stack
        ORG 0040H
        LHI HIGH RSP
        LLI LOW RSP
        LMI 0
        INL
        LMI 3FH
        LAI LOW STOP
        LBI HIGH STOP
        CAL PUSH
        JMP SC_6D61696E
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
; C/D are preserved, E is scratch. Byte locals may leave the RAM stack unaligned.
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
; PUSH/POP preserve C/D and handle odd stack addresses/page crossings.
; Only update the pointer high byte on a borrow/carry; loads preserve carry.
; Keep the PUSH bounds check on both paths, including the no-borrow path.
; POP and SCRETURN copy the old pointer low byte to E rather than rereading RAM.
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
        JFZ PUSHWORD
        INH
PUSHWORD:
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
        JFZ POPWORD
        INH
POPWORD:
        LBM
        RET
LD1:    CAL POP
        LHB
        LLA
        LAM
        LBI 0
        JMP PUSH
LD2:    CAL POP
        LHB
        LLA
        LAM
        INL
        JFZ SCINC9
        INH
SCINC9:
        LBM
        JMP PUSH
ST1:    CAL POP
        LCA
        LDB
        CAL POP
        LHD
        LLC
        LMA
        RET
ST2:    CAL POP
        LCA
        LDB
        CAL POP
        LHD
        LLC
        LMA
        INL
        JFZ SCINC10
        INH
SCINC10:
        LMB
        RET
DUP2:   CAL LOADSP
        LAM
        INL
        JFZ SCINC11
        INH
SCINC11:
        LBM
        JMP PUSH
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
NEGI:   CAL POP
        CAL NEG
        JMP PUSH
COM:    CAL POP
        XRI 0FFH
        LEA
        LAB
        XRI 0FFH
        LBA
        LAE
        JMP PUSH
SX1:    CAL POP
        LBI 0
        NDA
        JFS SXDONE
        LBI 0FFH
SXDONE: JMP PUSH
ZX1:    CAL POP
        LBI 0
        JMP PUSH
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
STACKMSG: DB "Small C stack overflow",13D,0
DIVMSG: DB "Small C division by zero",13D,0

ADD:
        LCA
        LDB
        CAL POP
        ADC
        LEA
        LAB
        ACD
        LBA
        LAE
        RET
SUB:
        LCA
        LDB
        CAL POP
        SUC
        LEA
        LAB
        SBD
        LBA
        LAE
        RET
BAND:
        LCA
        LDB
        CAL POP
        NDC
        LEA
        LAB
        NDD
        LBA
        LAE
        RET
BOR:
        LCA
        LDB
        CAL POP
        ORC
        LEA
        LAB
        ORD
        LBA
        LAE
        RET
BXOR:
        LCA
        LDB
        CAL POP
        XRC
        LEA
        LAB
        XRD
        LBA
        LAE
        RET
LSHIFT:
        LCA
        CAL POP
LSHIFTLOOP:
        LEA
        LAC
        NDA
        JTZ LSHIFTDONE
        DCC
        LAE
        ADA
        LEA
        LAB
        RAL
        LBA
        LAE
        JMP LSHIFTLOOP
LSHIFTDONE: LAE
        RET
SHRI:
        LCA
        CAL POP
SHRILOOP:
        LEA
        LAC
        NDA
        JTZ SHRIDONE
        DCC
        LAE
        LAB
        NDA
        RLC
        LAB
        RAR
        LBA
        LAE
        RAR
        JMP SHRILOOP
SHRIDONE: LAE
        RET
SHRU:
        LCA
        CAL POP
SHRULOOP:
        LEA
        LAC
        NDA
        JTZ SHRUDONE
        DCC
        LAE
        LAB
        NDA
        RAR
        LBA
        LAE
        RAR
        JMP SHRULOOP
SHRUDONE: LAE
        RET; The compiler tracks offsets relative to SP. Only one return word is pushed.
SPADDR: CAL LOADSP
        LCL
        LDH
        ADC
        LEA
        LAB
        ACD
        LBA
        LAE
        RET
SWAP:   LEA
        LAC
        LCE
        LAE
        LEA
        LAB
        LBD
        LDA
        LAE
        RET
; Consume the return word directly, retaining AB in CD. Keep the odd-address
; page guard used by POP; no nested hardware call is needed here.
SCRETURN:
        LCA
        LDB
        LHI HIGH RSP
        LLI LOW RSP
        LAM
        LEA
        ADI 2
        LMA
        INL
        LBM
        JFC SCRETREADY
        INB
        LMB
        DCB
SCRETREADY:
        LHB
        LLE
        LAM
        INL
        JFZ SCRETWORD
        INH
SCRETWORD:
        LBM
        LHI HIGH SCRETJ
        LLI LOW SCRETJ+1
        LMA
        INL
        LMB
        LAC
        LBD
SCRETJ: JMP 0
JUMPAB: LHI HIGH SCINDJ
        LLI LOW SCINDJ+1
        LMA
        INL
        LMB
SCINDJ: JMP 0
; putchar/getchar/puts use the Small C ABI, not the ACK frame convention.
SC_70757463686172:
        LAI 2
        LBI 0
        CAL SPADDR
        LHB
        LLA
        LAM
        LBI 0
        CAL SCPRINT
        JMP SCRETURN
SCPRINT:
        CPI 10D
        JFZ SCPRINTBYTE
        LAI 13D
SCPRINTBYTE:
        OUT 12
        RET
; kbhit() returns nonzero when getchar() will not block (default console ports).
SC_6B62686974:
        INP 1
        LBI 0
        JMP SCRETURN
; waitkey(ticks): poll for approximately ticks milliseconds at 500 kHz.
; ticks is 0..255; return the last character received, or -1 if there was none.
; Each empty tick is 524 clocks except the final tick (520). Input adds clocks.
SC_776169746B6579:
        LAI 2
        LBI 0
        CAL SPADDR
        LHB
        LLA
        LEM
        LCI 0FFH
        LAE
        NDA
        JTZ SCWAITDONE
SCWAITOUTER:
        LDI 6
SCWAITLOOP:
        INP 1
        NDA
        JTZ SCWAITNEXT
        INP 2
        NDI 7FH
        LCA
SCWAITNEXT:
        DCD
        JFZ SCWAITLOOP
        DCE
        JFZ SCWAITOUTER
SCWAITDONE:
        LAC
        LBI 0
        CPI 0FFH
        JFZ SCWAITRETURN
        LBI 0FFH
SCWAITRETURN:
        JMP SCRETURN
SC_67657463686172:
        INP 2
        NDI 7FH
        CPI 13D
        JFZ SCGOTCHAR
        LAI 10D
SCGOTCHAR:
        LBI 0
        JMP SCRETURN
SC_70757473:
        LAI 2
        LBI 0
        CAL SPADDR
        LHB
        LLA
        LAM
        INL
        JFZ SCPSADDR
        INH
SCPSADDR:
        LHM
        LLA
SCPSLOOP:
        LAM
        NDA
        JTZ SCPSDONE
        CAL SCPRINT
        INL
        JFZ SCPSLOOP
        INH
        JMP SCPSLOOP
SCPSDONE:
        LAI 13D
        OUT 12
        LAI 0
        LBI 0
        JMP SCRETURN
; Switch scan: CD is the value. X points at the next [value,target] pair.
SCSWITCH:
        LCA
        LDB
        CAL POP
        LHI HIGH X
        LLI LOW X
        LMA
        INL
        LMB
SCSWNEXT:
        LHI HIGH X
        LLI LOW X
        LAM
        INL
        LHM
        LLA
        LAM
        LEA
        INL
        JFZ SCSW1
        INH
SCSW1:  LBM
        INL
        JFZ SCSW2
        INH
SCSW2:  LAM
        LHI HIGH Q
        LLI LOW Q
        LMA
        ; Recover the pointer for the target's high byte.
        LHI HIGH X
        LLI LOW X
        LAM
        ADI 3
        LEA
        INL
        LAM
        ACI 0
        LHA
        LLE
        LAM
        LHI HIGH Q
        LLI LOW Q+1
        LMA
        ; Q == 0 marks the default; its address is the preceding value.
        LLI LOW Q
        LAM
        INL
        ORM
        JTZ SCSWDEFAULT
        ; Reload case value (the scan above reused E).
        LLI LOW X
        LAM
        INL
        LHM
        LLA
        LAM
        CPC
        JFZ SCSWADV
        INL
        JFZ SCSW3
        INH
SCSW3:  LAM
        CPD
        JTZ SCSWMATCH
SCSWADV:
        LHI HIGH X
        LLI LOW X
        LAM
        ADI 4
        LMA
        INL
        LAM
        ACI 0
        LMA
        JMP SCSWNEXT
SCSWMATCH:
        LHI HIGH Q
        LLI LOW Q
        LAM
        INL
        LBM
        JMP JUMPAB
SCSWDEFAULT:
        LLI LOW X
        LAM
        INL
        LHM
        LLA
        LAM
        INL
        JFZ SCSW4
        INH
SCSW4:  LBM
        JMP JUMPAB

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
