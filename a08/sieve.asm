; Native 8008 port of https://github.com/davidly/cpm_compilers/blob/main/asm/SIEVE.ASM.
; BYTE odd-number sieve: ten passes, SIZE=8190, with one padding byte.
; HL scans flags+i; BC saves it, DE = 2*i+3, HL = flags+k. No keyboard or CP/M calls.
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
        LAI 1
; Sixteen flags per branch; the 8192-byte region is page aligned.
FILL:   LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        LMA
        INL
        JFZ FILL
        INH
        LAH
        CPI 038H
        LAI 1                  ; flags are unchanged by loads
        JFZ FILL
        LHI HIGH FLAGS         ; L is zero after the fill
        XRA
; HL walks eight flags per branch; only the eighth INL can wrap L.
; A stays zero while scanning: CPM tests a flag, and CFZ calls PRIME.
SCAN:   CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        CPM
        CFZ PRIME
        INL
        JFZ SCAN
        INH
        LAH
        CPI 038H
        LAI 0
        JFZ SCAN
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
; BC saves the flag pointer. DE = 2*i+3, where i = HL-FLAGS.
PRIME:  LBH
        LCL
        LAL
        ADL
        LEA
        LAH
        ACH
        SUI 2*HIGH FLAGS
        LDA
        LAE
        ADI 3
        LEA
        JFC STEPDONE
        IND
STEPDONE:
        LAD
        NDA
        JFZ KBIG
; D is zero: only a low-byte carry changes H, and LMD clears a flag.
; A tracks L between marks. Eight copies fall through on the common
; no-carry path; each carry handler resumes the correct next copy.
        LAL
        JMP KS7
KM0:    LMD
KS0:    ADE
        LLA
        JTC KC0
KM1:    LMD
KS1:    ADE
        LLA
        JTC KC1
KM2:    LMD
KS2:    ADE
        LLA
        JTC KC2
KM3:    LMD
KS3:    ADE
        LLA
        JTC KC3
KM4:    LMD
KS4:    ADE
        LLA
        JTC KC4
KM5:    LMD
KS5:    ADE
        LLA
        JTC KC5
KM6:    LMD
KS6:    ADE
        LLA
        JTC KC6
KM7:    LMD
KS7:    ADE
        LLA
        JFC KM0
KC7:    INH
        LAH
        CPI 038H
        LAL
        JTC KM0
        JMP COUNT
KC0:    INH
        LAH
        CPI 038H
        LAL
        JTC KM1
        JMP COUNT
KC1:    INH
        LAH
        CPI 038H
        LAL
        JTC KM2
        JMP COUNT
KC2:    INH
        LAH
        CPI 038H
        LAL
        JTC KM3
        JMP COUNT
KC3:    INH
        LAH
        CPI 038H
        LAL
        JTC KM4
        JMP COUNT
KC4:    INH
        LAH
        CPI 038H
        LAL
        JTC KM5
        JMP COUNT
KC5:    INH
        LAH
        CPI 038H
        LAL
        JTC KM6
        JMP COUNT
KC6:    INH
        LAH
        CPI 038H
        LAL
        JTC KM7
        JMP COUNT
KBMARK: LMI 0
KBIG:   LAL
        ADE
        LLA
        LAH
        ACD
        LHA
        CPI 038H
        JTC KBMARK
COUNT:  LHI HIGH VARS
        LLI 0
        LAM
        ADI 1
        LMA
        JFC RESUME             ; high byte changes only on carry
        INL
        LAM
        ACI 0
        LMA
RESUME: LHB
        LLC
        XRA
        RET
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
