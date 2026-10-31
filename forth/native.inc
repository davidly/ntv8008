; Native additions for packed flags. Upstream files remain unchanged.
name_SHIFT3:    linklast CFAT
                db 7,'3','R','S','H','I','F','T'
cw_SHIFT3:      db lo(code_SHIFT3),hi(code_SHIFT3)
code_SHIFT3:    pop_ba
                call shift3_ba
                push_ba
                jmp next
; Unsigned BA >> 3; C, D and E are preserved.
shift3_ba:
                mov l,a
                mov a,b
                ora a
                rar
                mov b,a
                mov a,l
                rar
                mov l,a
                mov a,b
                ora a
                rar
                mov b,a
                mov a,l
                rar
                mov l,a
                mov a,b
                ora a
                rar
                mov b,a
                mov a,l
                rar
                ret
name_BITFETCH:  linklast SHIFT3
                db 4,'B','I','T','@'
cw_BITFETCH:    db lo(code_BITFETCH),hi(code_BITFETCH)
code_BITFETCH:  call bit_address
                mov a,m
                ana c
                mvi b,0
                push_ba
                e_restore
                jmp next
name_BITCLEAR:  linklast BITFETCH
                db 6,'B','I','T','C','L','R'
cw_BITCLEAR:    db lo(code_BITCLEAR),hi(code_BITCLEAR)
code_BITCLEAR:  call bit_address
                mov a,c
                xri 255
                ana m
                mov m,a
                e_restore
                jmp next
; ( base unsigned-bit-index -- ) -> HL byte address, C mask.
; Save return-stack pointer E while using it as an address temporary.
bit_address:   e_save
                pop_ba
                mov e,a
                ani 7
                mov c,a
                ora a
                mvi a,1
                jz bit_mask_done
bit_mask_loop: rlc
                dcr c
                jnz bit_mask_loop
bit_mask_done: mov c,a
                mov a,e
                call shift3_ba
                mvi h,dstackpage
                dstackptr_get
                add m
                mov e,a
                inr l
                mov a,m
                adc b
                mov h,a
                mov l,e
                skip_ds
                ret
