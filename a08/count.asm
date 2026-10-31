; Exercise arithmetic, conditional control, RAM and all four rotates.
        ORG 000#100
        LHI 077
        LLI 0377
        LMI 060
        LBI 012
LOOP:   LAM
        OUT 12
        ADI 1
        LMA
        DCB
        JFZ LOOP
        LAI 012
        OUT 12
        LAI 0201
        RLC
        RRC
        RAL
        RAR
        CPI 0201
        JFZ FAIL
        HLT
FAIL:   LAI 041
        OUT 12
        HLT
        END
