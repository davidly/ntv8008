; A08 syntax. All unmarked numbers are OCTAL; 0040H is hexadecimal.
; Console input is port 2; output is decimal 10, written as octal 12.
        ORG 0040H
        LHI HIGH PROMPT
        LLI LOW PROMPT
        CAL PRINT
        INP 2
        NDI 177                 ; discard the input-ready flag
        OUT 12                  ; echo the character ourselves
        SUI 060                 ; ASCII '0' -> array index
        CPI 4
        JFC BAD                 ; reject indices outside 0..3
        LBA                     ; B holds the checked index
        LAI 012
        OUT 12
        LHI HIGH SQUARES
        LLI LOW SQUARES
        LAB
        ADL
        LLA
        JFC FOUND
        INH                     ; address addition may cross a page
FOUND:  LAM
        LBA                     ; B holds the square while PRINT uses A/HL
        LHI HIGH RESULT
        LLI LOW RESULT
        CAL PRINT
        LAB
        ADI 060                 ; all four squares fit in one decimal digit
        OUT 12
        LAI 012
        OUT 12
        HLT
BAD:    LAI 012
        OUT 12
        LHI HIGH ERROR
        LLI LOW ERROR
        CAL PRINT
        HLT

; Print the zero-terminated string at HL. Clobbers A, H, L and flags.
; Only one hardware return slot is needed; PRINT never calls another routine.
PRINT:  LAM
        CPI 0
        RTZ
        OUT 12
        INL
        JFZ PRINT
        INH
        JMP PRINT

PROMPT: DATA "8008 SQUARE TABLE", 012, "Choose 0..3:", 012, 0
RESULT: DATA "SQUARE =", 012, 0
ERROR:  DATA "USE A DIGIT FROM 0 TO 3.", 012, 0
SQUARES: DATA 0, 1, 4, 011        ; 011 octal is 9 decimal
        END
