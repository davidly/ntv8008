; Sum 1 through 10; B=sum, C=next addend, D=decimal tens.
; A08 unmarked constants are octal.
        ORG 0040H
        LBI 0
        LCI 1
LOOP:   LAB
        ADC
        LBA
        INC
        LAC
        CPI 013
        JFZ LOOP
        LDI 0
        LAB
TENS:   CPI 012
        JTC DIGITS
        SUI 012
        IND
        JMP TENS
DIGITS: LBA
        LAD
        ADI 060
        OUT 12
        LAB
        ADI 060
        OUT 12
        LAI 012
        OUT 12
        HLT
        END
