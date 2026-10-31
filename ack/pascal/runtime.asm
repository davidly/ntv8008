; Static link is the first argument, at FP+4, in nested Pascal procedures.
; PCLEX follows A links and returns HL = enclosing native frame pointer.
PCMASK EQU RSP+26D
F_PCHALT: HLT
PCLEX:  LCA
        LHI HIGH FP
        LLI LOW FP
        LEM
        INL
        LHM
        LLE
PCLEXLOOP:
        LAC
        NDA
        RTZ
        DCC
        LAL
        ADI 4
        LLA
        LAH
        ACI 0
        LHA
        LAM
        INL
        LHM
        LLA
        JMP PCLEXLOOP

; Pascal MOD requires a positive divisor and a nonnegative remainder.
PMDIV EQU RSP+28D
PMODI:  CAL PMCHECK
        CAL MODI
        JMP PMADJUST
PMODSAVE:
        CAL PMCHECK
        CAL RMISAVE
        JMP PMADJUST
PMCHECK:
        LEA
        LAB
        NDA
        JTS PMBAD
        ORE
        JTZ PMBAD
        LHI HIGH PMDIV
        LLI LOW PMDIV
        LME
        INL
        LMB
        LAE
        RET
PMADJUST:
        LEA
        LAB
        NDA
        LAE
        RFS
        LHI HIGH PMDIV
        LLI LOW PMDIV
        ADM
        LEA
        INL
        LAB
        ACM
        LBA
        LAE
        RET
PMBAD:  LHI HIGH PMMSG
        LLI LOW PMMSG
        JMP TRAPMSG
PMMSG:  DB "Pascal invalid MOD divisor",13D,0
