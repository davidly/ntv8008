"""Auditable, idempotent patches to the pinned BASIC frontend."""

def apply(root):
    directory = root/'lang/basic/src'
    def edit(name,old,new):
        path=directory/name
        text=path.read_text()
        if new in text:
            return
        if text.count(old)!=1:
            raise ValueError('unexpected ACK BASIC source: '+name)
        path.write_text(text.replace(old,new))
    edit('parsepar.c','int\tnolins=0;', 'int i8008=0;\nint\tnolins=0;')
    edit('parsepar.c',"\t\t\t\tcase 'D':", "\t\t\t\tcase '8': i8008=1; break;\n\t\t\t\tcase 'D':")
    edit('bem.h','extern int\tnolins;', 'extern int i8008;\nextern int\tnolins;')
    edit('gencode.c','\tC_ms_par((arith)0);', '''\tC_ms_par((arith)0);
    if (i8008) {
        /* No hosted signals, setjmp, or DATA file channels on this target. */
        datfile = fopen(datfname, "w+b");
        if (!datfile) fatal("improper file creation permission");
        return;
    }''')
    edit('gencode.c','C_rom_cst((arith)(myitoa(strlen(datfname))));',
         'C_rom_cst((arith)strlen(datfname));')
    edit('symbols.c','for(i=first;i<=last;i++) deftype[(unsigned char)i]= type;',
         'for(i=first;i<=last;i++) { deftype[(unsigned char)tolower(i)]=type; deftype[(unsigned char)toupper(i)]=type; }')
    edit('symbols.c','else deftype[(unsigned char)first]=type;',
         'else { deftype[(unsigned char)tolower(first)]=type; deftype[(unsigned char)toupper(first)]=type; }')
    edit('symbols.c','if ( s->symtype==DEFAULTTYPE) s->symtype= DOUBLETYPE;',
         'if ( s->symtype==DEFAULTTYPE) s->symtype= deftype[(unsigned char)*s->symname];')
    helper='''
/* Compare integer FOR bounds directly; sign multiplication overflows at MININT. */
static void integer_for_test(struct FORSTRUCT *f, int address)
{
    label negative=genlabel(), done=genlabel();
    C_lae_dlb((label)f->stepaddress,(arith)0); loadvar(INTTYPE);
    C_zlt(negative);
    C_lae_dlb((label)address,(arith)0); loadvar(INTTYPE);
    C_lae_dlb((label)f->limitaddress,(arith)0); loadvar(INTTYPE);
    C_cmi((arith)BEMINTSIZE); C_zgt((label)f->forout); C_bra(done);
    C_df_ilb(negative);
    C_lae_dlb((label)address,(arith)0); loadvar(INTTYPE);
    C_lae_dlb((label)f->limitaddress,(arith)0); loadvar(INTTYPE);
    C_cmi((arith)BEMINTSIZE); C_zlt((label)f->forout);
    C_df_ilb(done);
}
'''
    edit('gencode.c','int\tforcnt= -1;', 'int\tforcnt= -1;\n'+helper)
    edit('gencode.c','type= f->loopvar->symtype;\n\t/* evaluate lower',
         'type= f->loopvar->symtype;\n    if (i8008 && type==INTTYPE) { integer_for_test(f,f->initaddress); return; }\n\t/* evaluate lower')
    edit('gencode.c','C_df_ilb((label)f->fortst);\n\tC_lae_dlb',
         'C_df_ilb((label)f->fortst);\n    if (i8008 && result==INTTYPE) { integer_for_test(f,varaddress); return; }\n\tC_lae_dlb')
    edit('gencode.c','void pokestmt(int type1,int type2)\n{',
         'void pokestmt(int type1,int type2)\n{\n    if (i8008) { error("POKE is unsupported on this target"); return; }')
