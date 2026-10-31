; Original keyboard/console demonstration. EOF exits through the host.
        ORG 0040H
        LAI 'E'
        OUT 12
        LAI 'C'
        OUT 12
        LAI 'H'
        OUT 12
        LAI 'O'
        OUT 12
        LAI '>'
        OUT 12
        LAI ' '
        OUT 12
AGAIN:  INP 2
        NDI 177
        OUT 12
        JMP AGAIN
        END
