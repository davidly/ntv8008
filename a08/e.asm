; Native 8008 port of https://github.com/davidly/cpm_compilers/blob/main/asm/E.ASM.
; Same factorial-series decimal spigot, DIGITS=200. No keyboard or CP/M.
; B = n, C = quotient, DA = x. Each array element fits in a byte.
; The outer-loop limit deliberately matches the 8080 source.
DIGITS  EQU 200D
ARRAY   EQU 1200H              ; page after MUL10HI; DIGITS must be 10..255
HIGHVAL EQU 1300H
        ORG 0040H
        LHI HIGH ARRAY
        LLI DIGITS-1
        LBI DIGITS-1
AINIT:  LMI 1
        DCL
        DCB
        JFZ AINIT
        LMI 0
        INL
        LMI 2
        LHI HIGH HIGHVAL
        LLI LOW HIGHVAL
        LMI DIGITS
OUTER:  LHI HIGH HIGHVAL
        LLI LOW HIGHVAL
        LAM
        SUI 1
        LMA
        LBA
        LHI HIGH ARRAY
        LDI 0
        XRA                    ; x = DA = 0
; Unsigned DA / B: quotient C, remainder A. The low byte stays in A;
; a low-byte borrow decrements D, and D going negative ends the division.
INNER:  LCI 0FFH
UDIV:   INC
        SUB
        JTC BORROW
        INC
        SUB
        JFC UDIV
BORROW: DCD
        JFS UDIV
        ADB                    ; undo the failed subtraction; D is dead
        LLB
        LMA                    ; a[n] = x MOD n
        DCL
        LLM                    ; index by a[n-1]
        LHI HIGH MUL10LO
        LAM
        INH
        LDM                    ; DA = 10*a[n-1], preserving n and quotient
        INH                    ; back to ARRAY for the next n
        ADC                    ; x = 10*a[n-1] + quotient
        JTC XCARRY
        DCB
        JFZ INNER
        JMP DIGIT
XCARRY: IND
        DCB
        JFZ INNER
DIGIT:  LEA
        CAL PUTU
        LHI HIGH HIGHVAL
        LLI LOW HIGHVAL
        LAM
        CPI 9D
        JFZ OUTER
        LHI HIGH MESSAGE
        LLI LOW MESSAGE
        CAL PRINT
        HLT
MESSAGE: DATA 012, "done.", 012, 0
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

; PUTU emits the spigot's small nonnegative result (DE < 100).
; Only the first outer iteration can use the initial a[1]=2.
PUTU:   LBI '0'
        LAE
ETENS:  CPI 10D
        JTC EDIGITS
        SUI 10D
        INB
        JMP ETENS
EDIGITS:
        LEA
        LAB
        CPI '0'
        JTZ EUNITS
        OUT 12
EUNITS: LAE
        ADI '0'
        OUT 12
        RET
; Two adjacent pages contain LOW/HIGH (10*n) for every byte n.
; This replaces repeated 16-bit doubling without changing the spigot.
        ORG 1000H
MUL10LO:
        DATA 0D,10D,20D,30D,40D,50D,60D,70D,80D,90D,100D,110D,120D,130D,140D,150D
        DATA 160D,170D,180D,190D,200D,210D,220D,230D,240D,250D,4D,14D,24D,34D,44D,54D
        DATA 64D,74D,84D,94D,104D,114D,124D,134D,144D,154D,164D,174D,184D,194D,204D,214D
        DATA 224D,234D,244D,254D,8D,18D,28D,38D,48D,58D,68D,78D,88D,98D,108D,118D
        DATA 128D,138D,148D,158D,168D,178D,188D,198D,208D,218D,228D,238D,248D,2D,12D,22D
        DATA 32D,42D,52D,62D,72D,82D,92D,102D,112D,122D,132D,142D,152D,162D,172D,182D
        DATA 192D,202D,212D,222D,232D,242D,252D,6D,16D,26D,36D,46D,56D,66D,76D,86D
        DATA 96D,106D,116D,126D,136D,146D,156D,166D,176D,186D,196D,206D,216D,226D,236D,246D
        DATA 0D,10D,20D,30D,40D,50D,60D,70D,80D,90D,100D,110D,120D,130D,140D,150D
        DATA 160D,170D,180D,190D,200D,210D,220D,230D,240D,250D,4D,14D,24D,34D,44D,54D
        DATA 64D,74D,84D,94D,104D,114D,124D,134D,144D,154D,164D,174D,184D,194D,204D,214D
        DATA 224D,234D,244D,254D,8D,18D,28D,38D,48D,58D,68D,78D,88D,98D,108D,118D
        DATA 128D,138D,148D,158D,168D,178D,188D,198D,208D,218D,228D,238D,248D,2D,12D,22D
        DATA 32D,42D,52D,62D,72D,82D,92D,102D,112D,122D,132D,142D,152D,162D,172D,182D
        DATA 192D,202D,212D,222D,232D,242D,252D,6D,16D,26D,36D,46D,56D,66D,76D,86D
        DATA 96D,106D,116D,126D,136D,146D,156D,166D,176D,186D,196D,206D,216D,226D,236D,246D
MUL10HI:
        DATA 0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,0D
        DATA 0D,0D,0D,0D,0D,0D,0D,0D,0D,0D,1D,1D,1D,1D,1D,1D
        DATA 1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D,1D
        DATA 1D,1D,1D,1D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D
        DATA 2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,2D,3D,3D,3D
        DATA 3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D,3D
        DATA 3D,3D,3D,3D,3D,3D,3D,4D,4D,4D,4D,4D,4D,4D,4D,4D
        DATA 4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D,4D
        DATA 5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,5D
        DATA 5D,5D,5D,5D,5D,5D,5D,5D,5D,5D,6D,6D,6D,6D,6D,6D
        DATA 6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D,6D
        DATA 6D,6D,6D,6D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D
        DATA 7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,7D,8D,8D,8D
        DATA 8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D,8D
        DATA 8D,8D,8D,8D,8D,8D,8D,9D,9D,9D,9D,9D,9D,9D,9D,9D
        DATA 9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D,9D
        END
