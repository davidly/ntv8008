; Native 8008 port of https://github.com/davidly/cpm_compilers/blob/main/asm/SIEVE.ASM.
; BYTE odd-number sieve: ten passes, SIZE=8190, with one padding byte.
; BC = i, DE = 2*i+3, HL = flags+i / flags+k. No keyboard or CP/M calls.
; Expected output: 1899 primes.
LOOPS   EQU 10D
FLAGS   EQU 1800H              ; 8192 bytes, ending at 3800H (exclusive)
VARS    EQU 1400H              ; count low, count high, completed passes
        ORG 0040H
        LHI HIGH VARS
        LLI 2
        LMI 0
ITERAGAIN:
        LHI HIGH VARS
        LLI 0
        LMI 0
        INL
        LMI 0
        LHI HIGH FLAGS
        LLI 0
; Sixteen flags per branch; the 8192-byte region is page aligned.
FILL:   LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        LMI 1
        INL
        JFZ FILL
        INH
        LAH
        CPI 038H
        JFZ FILL
        LBI 0
        LCI 0
NEXTPRIME:
        LAB
        ADI HIGH FLAGS
        LHA
        LLC
        LAM
        NDA
        JTZ NEXTI
        ; DE = BC + BC + 3, using low-byte carry into the high byte.
        LAC
        ADC
        LEA
        LAB
        ACB
        LDA
        LAE
        ADI 3
        LEA
        LAD
        ACI 0
        LDA
KLOOP:  LAL
        ADE
        LLA
        LAH
        ACD
        LHA
        CPI 038H
        JFC INCCOUNT
        LMI 0
        JMP KLOOP
INCCOUNT:
        LHI HIGH VARS
        LLI 0
        LAM
        ADI 1
        LMA
        JFC NEXTI          ; high byte changes only on carry
        INL
        LAM
        ACI 0
        LMA
NEXTI:  INC
        JFZ NEXTPRIME
        INB
        LAB
        CPI 020H
        JFZ NEXTPRIME
        LHI HIGH VARS
        LLI 2
        LAM
        ADI 1
        LMA
        CPI LOOPS
        JFZ ITERAGAIN
        LLI 0
        LEM
        INL
        LDM
        CAL PUTU
        LHI HIGH MESSAGE
        LLI LOW MESSAGE
        CAL PRINT
        HLT
MESSAGE: DATA " primes.", 012, 0
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
        END
