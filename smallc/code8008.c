/* SmallC-85 native 8008 backend. The renderer expands immediates and
 * software calls into A08 instructions; no 8080 code is generated. */
#include <stdio.h>
#include "defs.h"
#include "data.h"

static void op(char *s) { output_line(s); }
static void operand(char *s, char *v) {
    output_with_tab(s); output_string(v); newline();
}
static void number(char *s, int n) {
    output_with_tab(s); output_decimal(n); newline();
}
static void binary(char *s) { op(s); stkp += INTSIZE; }
static int width(SYMBOL *s) {
    return s->identity != POINTER && (s->type & CCHAR) ? 1 : 2;
}
void header() { op("; SmallC-85 / native Intel 8008"); }
int newline() { output_byte(LF); return 0; }
void initmac() { defmac("smallc\t1"); defmac("I8008\t1"); }
void output_label_prefix() { output_byte('$'); }
void output_label_terminator() { output_byte(':'); }
void gen_comment() { output_byte(';'); }
void trailer() {}
void code_segment_gtext() { op("TEXT"); }
void data_segment_gdata() { op("DATA"); }
void ppubext(SYMBOL *s) {}
void fpubext(SYMBOL *s) {}
void output_number(int n) { output_decimal(n); }
void gen_get_memory(SYMBOL *s) {
    operand("IMM ", s->name);
    number("LOAD ", width(s) == 1 && s->type == CCHAR ? -1 : width(s));
}
int gen_get_locale(SYMBOL *s) {
    if (s->storage == LSTATIC) {
        output_with_tab("IMM "); print_label(s->offset); newline();
    } else number("ADDRSP ", s->offset - stkp);
    return HL_REG;
}
void gen_put_memory(SYMBOL *s) {
    output_with_tab("STORE "); output_string(s->name);
    output_byte(','); output_decimal(width(s)); newline();
}
void gen_put_indirect(char t) { number("STIND ", (t & CCHAR) ? 1 : 2); stkp += 2; }
void gen_get_indirect(char t, int reg) { number("LOAD ", t == CCHAR ? -1 : t == UCHAR ? 1 : 2); }
int gen_swap() { op("SWAP"); return 0; }
int gen_immediate() { output_with_tab("IMM "); return 0; }
int gen_immediate2() { output_with_tab("SECOND "); return 0; }
int gen_push(int reg) { op("PUSH"); stkp -= 2; return 0; }
int gen_pop() { op("POPSECOND"); stkp += 2; return 0; }
int gen_swap_stack() { op("SWAPSTACK"); return 0; }
int gen_call(char *s) { operand("CALL ", s); return 0; }
int declare_entry_point(char *s) { operand("; FUNCTION ", s); output_string(s); output_label_terminator(); return 0; }
int gen_ret() { op("RETURN"); return 0; }
int callstk() { op("CALLIND"); stkp += 2; return 0; }
int gen_jump(int l) { output_with_tab("JUMP "); print_label(l); newline(); return 0; }
int gen_test_jump(int l, int ft) {
    output_with_tab(ft ? "JTRUE " : "JFALSE "); print_label(l); newline(); return 0;
}
int gen_def_byte() { output_with_tab("DB "); return 0; }
int gen_def_word() { output_with_tab("DW "); return 0; }
int gen_def_storage() { output_with_tab("DS "); return 0; }
int gen_modify_stack(int n) { if (n != stkp) number("ADJSP ", n-stkp); return n; }
int gen_multiply_by_two() { op("DOUBLE"); return 0; }
int gen_divide_by_two() { op("HALF"); return 0; }
int gen_jump_case() { op("SWITCH"); return 0; }
int gen_add(LVALUE *a, LVALUE *b) {
    if (dbltest(b,a)) op("SCALESECOND");
    binary("ADD"); return 0;
}
int gen_sub() { binary("SUB"); return 0; }
int gen_mult() { binary("MUL"); return 0; }
int gen_div() { binary("DIVI"); return 0; }
int gen_udiv() { binary("DIVU"); return 0; }
int gen_mod() { binary("MODI"); return 0; }
int gen_umod() { binary("MODU"); return 0; }
int gen_or() { binary("BOR"); return 0; }
int gen_xor() { binary("BXOR"); return 0; }
int gen_and() { binary("BAND"); return 0; }
int gen_arithm_shift_right() { binary("SHRI"); return 0; }
int gen_logical_shift_right() { binary("SHRU"); return 0; }
int gen_arithm_shift_left() { binary("LSHIFT"); return 0; }
int gen_equal() { binary("EQ"); return 0; }
int gen_not_equal() { binary("NE"); return 0; }
int gen_less_than() { binary("LT"); return 0; }
int gen_less_or_equal() { binary("LE"); return 0; }
int gen_greater_than() { binary("GT"); return 0; }
int gen_greater_or_equal() { binary("GE"); return 0; }
int gen_unsigned_less_than() { binary("ULT"); return 0; }
int gen_unsigned_less_or_equal() { binary("ULE"); return 0; }
int gen_usigned_greater_than() { binary("UGT"); return 0; }
int gen_unsigned_greater_or_equal() { binary("UGE"); return 0; }
int gen_twos_complement() { op("NEGATE"); return 0; }
int gen_logical_negation() { op("NOT"); return 0; }
int gen_complement() { op("COMPLEMENT"); return 0; }
int gen_convert_primary_reg_value_to_bool() { op("BOOL"); return 0; }
int gen_increment_primary_reg(LVALUE *v) {
    number("OFFSET ", v->ptr_type == STRUCT ? v->tagsym->size :
        (v->ptr_type & CINT) ? 2 : 1); return 0;
}
int gen_decrement_primary_reg(LVALUE *v) {
    number("OFFSET ", -(v->ptr_type == STRUCT ? v->tagsym->size :
        (v->ptr_type & CINT) ? 2 : 1)); return 0;
}
char *inclib() { return ""; }
int gnargs(int n) { return 0; }
int assemble(char *s) { return 0; }
int link() { return 0; }
int add_offset(int n) { number("OFFSET ", n); return 0; }
int gen_multiply(int t, int n) {
    if (t == CINT || t == UINT) op("DOUBLE");
    else if (t == STRUCT) number("SCALE ", n);
    return 0;
}
