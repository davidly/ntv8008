"""Build-copy repairs for ACK's dormant Occam frontend; upstream notices remain."""
from pathlib import Path
import re
import tarfile

BUILD = '''from build.ab import export, simplerule
from build.c import cprogram
from glob import glob
from util.LLgen.build import llgen
llgen(name="llgen", srcs=["./occam.g"])
simplerule(name="lexer", ins=["./lex.l"], outs=["=lex.yy.c"],
           commands=["flex --noyywrap -t $[ins] > $[outs]"])
cprogram(name="em_occam", srcs=glob("lang/occam/comp/*.c")+glob("lang/occam/comp/*.h")+[".+llgen", ".+lexer"],
 deps=["h", "modules/h", "modules/src/system", "modules/src/em_code+lib_k", "modules/src/em_mes"],
 cflags=["-Wno-strict-prototypes", "-Wno-return-type", "-Wno-implicit-int", "-Wno-implicit-function-declaration"])
export(name="all", items={"$(PLATDEP)/em_occam$(EXT)": ".+em_occam"})
'''


def apply(ack):
    folder=Path(ack)/'lang/occam/comp'
    # Always patch a pristine build copy from bootstrap's verified archive.
    with tarfile.open(Path(ack).parents[1]/'ack.tar.gz') as archive:
        for member in archive.getmembers():
            if '/lang/occam/comp/' in member.name and member.isfile():
                (folder/Path(member.name).name).write_bytes(archive.extractfile(member).read())
    (folder/'build.py').write_text(BUILD)
    root=Path(ack)/'build.py'
    text=root.read_text()
    if 'lang/occam/comp+all' not in text:
        root.write_text(text.replace('\"lang/pc/comp+all\",', '\"lang/pc/comp+all\",\n        \"lang/occam/comp+all\",'))
    for name in ('expr.c','symtab.c','em.c','lex.l','occam.g','code.c','keytab.c'):
        p=folder/name
        s=p.read_text()
        s=s.replace('char *malloc(), *strcpy();','').replace('char *malloc();','').replace('char *strcpy();','')
        if '#include <string.h>' not in s:
            headers='#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
            s=s.replace('%{','%{\n'+headers,1) if name=='lex.l' else (s.replace('{\n','{\n'+headers,1) if name=='occam.g' else headers+s)
        if name=='em.c':
            s=s.replace('C_blm((arith) size);', 'if (size%wz) { C_loc((arith)size); C_cal(\"occam_copy\"); C_asp((arith)(2*pz+wz)); } else C_blm((arith) size);')
        if name=='em.c' and '#include <stdio.h>' not in s:
            s='#include <stdio.h>\n'+s
        s=re.sub(r'^main\(argc, argv\) register argc;', 'int main(argc, argv) register argc;', s, flags=re.M)
        s=re.sub(r'^(\s*)siz=left->arr_siz;', r'\1int siz=left->arr_siz;', s, flags=re.M)
        s=s.replace('case E_CALL: {\n\t\tsize=0;', 'case E_CALL: {\n\t\tint size=0;')
        s=s.replace('\n\t\toffset=form_offsets(', '\n\t\tint offset=form_offsets(')
        s=re.sub(r'^(\t+)([a-zA-Z_]\w*(?:, \w+)*)[;]$', lambda m:m[0] if m[2] in ('break','return','continue') else m[1]+'int '+m[2]+';', s, flags=re.M)
        if name=='occam.g':
            s=re.sub(r'^(\w+\()\*',r'\1int *',s,flags=re.M)
            s=s.replace('register *g_type','register int *g_type')
            s=s.replace('{\tLabel(END); }\n\t| WHILE', '{\tloc(3); trp(); Label(END); }\n\t| WHILE')
            s=s.replace('static errors=0;', 'static errors=0;\n\terr=1;')
        if name=='symtab.c':
            s=s.replace('warning(\"recursion not allowed\")','report(\"recursion not allowed\")')
        if name=='keytab.c':
            s=re.sub(r'\btrue\b','TRUE',s)
        if name=='expr.c':
            helper=("static long target_value(long value) {\n"
                    " if (vz==2) { value &= 65535L; if (value & 32768L) value-=65536L; }\n"
                    " return value;\n}\n")
            s=s.replace('static void rvalue()',helper+'\nstatic void rvalue()',1)
            s=s.replace('left->u.cst=lc;', 'left->u.cst=target_value(lc);')
            s=s.replace('pe->u.cst=cst;', 'pe->u.cst=target_value(cst);')
            s=s.replace("case BS:\tlc%=rc; break;", "case BS:\tif (rc==0L) report(\"division by zero\"); else lc%=rc; break;")
            s=s.replace("lc= (lc-rc)>0", "lc= target_value(lc-rc)>0")
            s=s.replace('lsiz=l->arr_siz, rsiz=r->arr_siz;', 'int lsiz=l->arr_siz, rsiz=r->arr_siz;')
            s=s.replace('\ttype= (l->type&T_TYPE)|byte;', '\tint type= (l->type&T_TYPE)|byte;')
        if name=='code.c':
            s=s.replace('warning(\"constant index outside vector\")', 'report(\"constant index outside vector\")')
            s=s.replace('if (!constant(e1) || !constant(e2)) {', 'if (!constant(e1) || !constant(e2) || (vz==2 && e1->u.cst+e2->u.cst>32767)) {')
            s=s.replace('if (constant(e1) && constant(e2)) {', 'if (constant(e1) && constant(e2) && !(vz==2 && e1->u.cst+e2->u.cst>32767)) {')
            s=re.sub(r'^(\s*)lsiz=left->arr_siz;',r'\1long lsiz=left->arr_siz;',s,flags=re.M)
            if '\tint offset;\n' not in s:
                s=s.replace('\tchar *des;\n','\tchar *des;\n\tint offset;\n')
            s=re.sub(r'^(\s*)offset=0;',r'\1int offset=0;',s,flags=re.M)
            s=re.sub(r'^(\s*)Default=0;',r'\1int Default=0;',s,flags=re.M)
        p.write_text(s)
    # Old K&R pseudo-varargs truncate pointers on 64-bit hosts.
    p=folder/'report.c'
    p.write_text('''/* Original ACK diagnostic module replaced for host varargs portability.
 * Copyright 1987 Vrije Universiteit; see upstream Copyright.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
extern int err, lineno;
extern char *curr_file;
static void diagnostic(char kind, const char *fmt, va_list ap) {
 fprintf(stderr, "%s (%d) %c: ", curr_file ? curr_file : "<input>", lineno, kind);
 vfprintf(stderr,fmt,ap); fputc('\\n',stderr);
}
void report(const char *fmt, ...) { va_list ap; va_start(ap,fmt); diagnostic('F',fmt,ap); va_end(ap); err=1; }
void warning(const char *fmt, ...) { va_list ap; va_start(ap,fmt); diagnostic('E',fmt,ap); va_end(ap); }
void fatal(const char *fmt, ...) { va_list ap; va_start(ap,fmt); diagnostic('X',fmt,ap); va_end(ap); exit(1); }
''')
