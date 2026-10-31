; A string crossing a page boundary, using CAL and RST. No keyboard needed.
        ORG 000#020
        OUT 12
        RET
        ORG 000#100
        LHI HIGH MESSAGE
        LLI LOW MESSAGE
        CAL PRINT
        HLT
PRINT:  LAM
        CPI 0
        RTZ
        RST 2
        INL
        JFZ PRINT
        INH
        JMP PRINT
        ORG 000#370
MESSAGE: DATA "HELLO, 8008!", 012, 0
        END
