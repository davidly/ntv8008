// Intel 8008 emulator. All memory is RAM; no wait states.
// Timing: Intel 8008 Users Manual, November 1972, section IV.
// Each T state takes two clock periods. The stack includes the active PC.

#include <string.h>
#include "i8008.hxx"

uint8_t memory[ 16384 ];

void I8008::power_on( uint16_t address )
{
    memset( r, 0, sizeof( r ) );
    memset( stack, 0, sizeof( stack ) );
    sp = 0;
    stack[ sp ] = address & 0x3fff;
    fCarry = fZero = fSign = fParity = false;
    halted = ended = invalid = false;
    m_state &= stateTrace;
    cycles = 0;
    m_previousSymbol = 0;
    if ( m_tracer )
        m_tracer->Trace( "power on, pc %04x\n", pc() );
} //power_on

I8008_FORCE_INLINE uint8_t I8008::fetch()
{
    uint8_t value = memory[ pc() ];
    stack[ sp ] = ( pc() + 1 ) & 0x3fff;
    return value;
} //fetch

I8008_FORCE_INLINE void I8008::set_reg( unsigned n, uint8_t value )
{
    if ( 7 == n )
        memory[ address() ] = value;
    else
        r[ n ] = value;
} //set_reg

I8008_FORCE_INLINE void I8008::set_szp( uint8_t value )
{
    fZero = ( 0 == value );
    fSign = ( 0 != ( value & 0x80 ) );
    // A byte lookup beats XOR folding in measured GCC/MSVC emulator runs.
    // True means an even number of set bits, including zero.
    static const bool evenParity[ 256 ] = {
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        false, true, true, false, true, false, false, true, true, false, false, true, false, true, true, false,
        true, false, false, true, false, true, true, false, false, true, true, false, true, false, false, true,
    };
    fParity = evenParity[ value ];
} //set_szp

I8008_FORCE_INLINE bool I8008::condition( uint8_t op ) const
{
    // Pack C/Z/S/P in condition-code order, avoiding a temporary bool array
    // and its indexed stack access. Keep the public named flag fields intact.
    unsigned flags = unsigned( fCarry ) | ( unsigned( fZero ) << 1 ) |
                     ( unsigned( fSign ) << 2 ) | ( unsigned( fParity ) << 3 );
    return ( ( flags >> ( ( op >> 3 ) & 3 ) ) & 1 ) == ( ( op >> 5 ) & 1u );
} //condition

I8008_FORCE_INLINE void I8008::alu( unsigned operation, uint8_t value )
{
    unsigned result = 0;
    switch ( operation )
    {
        case 0: result = r[ 0 ] + value; break;
        case 1: result = r[ 0 ] + value + fCarry; break;
        case 2: case 7: result = unsigned( r[ 0 ] ) - value; break;
        case 3: result = unsigned( r[ 0 ] ) - value - fCarry; break;
        case 4: result = r[ 0 ] & value; break;
        case 5: result = r[ 0 ] ^ value; break;
        case 6: result = r[ 0 ] | value; break;
    }
    fCarry = ( result > 255 ); // subtraction uses borrow, not inverted carry
    set_szp( (uint8_t) result );
    if ( 7 != operation )
        r[ 0 ] = (uint8_t) result;
} //alu

I8008_FORCE_INLINE unsigned I8008::execute_decoded( uint8_t op )
{
    unsigned states = 5;
    if ( op >= 0xc0 ) // Lrr, LrM, LMr, HLT
    {
        unsigned d = ( op >> 3 ) & 7, s = op & 7;
        if ( 7 == s ) // LrM or HLT (the LMM encoding)
        {
            if ( 7 == d ) // HLT
            {
                halted = true;
                m_state |= stateHalted;
                states = 4;
            }
            else // LrM
            {
                r[ d ] = memory[ address() ];
                states = 8;
            }
        }
        else if ( 7 == d ) // LMr
        {
            memory[ address() ] = r[ s ];
            states = 7;
        }
        else // Lrr
            r[ d ] = r[ s ];
    }
    else if ( op >= 0x80 ) // ADr, ACr, SUr, SBr, NDr, XRr, ORr, CPr (r includes M)
    {
        unsigned s = op & 7;
        alu( ( op >> 3 ) & 7, get_reg( s ) );
        states = ( 7 == s ) ? 8 : 5;
    }
    else if ( op >= 0x40 ) // INP, OUT, JMP, JFc, JTc, CAL, CFc, CTc
    {
        if ( op & 1 ) // INP or OUT
        {
            uint8_t port = ( op >> 1 ) & 31;
            if ( port < 8 ) // INP
                r[ 0 ] = i8008_input( port );
            else // OUT
                i8008_output( port, r[ 0 ] );
            states = ( port < 8 ) ? 8 : 6;
        }
        else // JMP, JFc, JTc, CAL, CFc, CTc
        {
            uint16_t target = fetch();
            target |= uint16_t( fetch() ) << 8;
            bool taken = ( 0 != ( op & 4 ) ) || condition( op ); // JMP/CAL unconditional; JFc/JTc/CFc/CTc conditional
            states = taken ? 11 : 9;
            if ( taken ) // JMP, JFc, JTc, CAL, CFc, CTc: branch taken
            {
                if ( op & 2 ) // CAL, CFc, CTc
                    sp = ( sp + 1 ) & 7;
                stack[ sp ] = target & 0x3fff;
            }
        }
    }
    else
    {
        switch ( op & 7 )
        {
            case 0: case 1: // INr, DCr, HLT
            {
                unsigned d = op >> 3;
                if ( 0 == d ) // HLT (00 and 01)
                {
                    halted = true;
                    m_state |= stateHalted;
                    states = 4;
                }
                else if ( d < 7 ) // INr, DCr: B, C, D, E, H, L only
                {
                    r[ d ] = uint8_t( r[ d ] + ( ( 0 == ( op & 1 ) ) ? 1 : -1 ) );
                    set_szp( r[ d ] );
                }
                else
                {
                    invalid = ended = true;
                    m_state |= stateEnded;
                }
                break;
            }
            case 2: // RLC, RRC, RAL, RAR
            {
                unsigned d = op >> 3;
                if ( d < 4 ) // RLC, RRC, RAL, RAR
                {
                    uint8_t a = r[ 0 ];
                    bool carry = fCarry;
                    fCarry = ( d & 1 ) ? ( 0 != ( a & 1 ) ) : ( 0 != ( a & 0x80 ) );
                    if ( d & 1 ) // RRC, RAR
                        r[ 0 ] = ( a >> 1 ) | ( ( d == 1 ? fCarry : carry ) << 7 );
                    else // RLC, RAL
                        r[ 0 ] = ( a << 1 ) | unsigned( d == 0 ? fCarry : carry );
                }
                else
                {
                    invalid = ended = true;
                    m_state |= stateEnded;
                }
                break;
            }
            case 3: // RFc, RTc
                if ( condition( op ) ) // RFc, RTc: return when the flag condition matches
                    sp = ( sp - 1 ) & 7;
                else
                    states = 3;
                break;
            case 4: alu( op >> 3, fetch() ); states = 8; break; // ADI, ACI, SUI, SBI, NDI, XRI, ORI, CPI
            case 5: // RST
                sp = ( sp + 1 ) & 7;
                stack[ sp ] = op & 0x38;
                break;
            case 6: // LrI, LMI
            {
                unsigned d = op >> 3;
                set_reg( d, fetch() );
                states = ( 7 == d ) ? 9 : 8;
                break;
            }
            case 7: sp = ( sp - 1 ) & 7; break; // RET
        }
    }
    return states;
} //execute_decoded

I8008_FORCE_INLINE unsigned I8008::execute( uint8_t op, bool injected )
{
    // The normal instruction path checks all stop/tracing conditions once.
    if ( m_state )
    {
        if ( m_state & ( stateHalted | stateEnded ) )
            return 0;
        trace_state( pc(), injected ? op : memory[ pc() ], injected );
    }
    uint16_t instructionAddress = pc();
    if ( !injected )
        op = fetch();
    // Constant operands let the compiler resolve register indices and ALU cases.
    // All instruction bodies remain in execute_decoded(); RAM is fetched afresh.
    unsigned states = 0;
    switch ( op )
    {
#define I8008_CASE( instruction ) case instruction: states = execute_decoded( instruction ); break;
        I8008_CASE( 0x00 ) I8008_CASE( 0x01 ) I8008_CASE( 0x02 ) I8008_CASE( 0x03 ) I8008_CASE( 0x04 ) I8008_CASE( 0x05 ) I8008_CASE( 0x06 ) I8008_CASE( 0x07 )
        I8008_CASE( 0x08 ) I8008_CASE( 0x09 ) I8008_CASE( 0x0a ) I8008_CASE( 0x0b ) I8008_CASE( 0x0c ) I8008_CASE( 0x0d ) I8008_CASE( 0x0e ) I8008_CASE( 0x0f )
        I8008_CASE( 0x10 ) I8008_CASE( 0x11 ) I8008_CASE( 0x12 ) I8008_CASE( 0x13 ) I8008_CASE( 0x14 ) I8008_CASE( 0x15 ) I8008_CASE( 0x16 ) I8008_CASE( 0x17 )
        I8008_CASE( 0x18 ) I8008_CASE( 0x19 ) I8008_CASE( 0x1a ) I8008_CASE( 0x1b ) I8008_CASE( 0x1c ) I8008_CASE( 0x1d ) I8008_CASE( 0x1e ) I8008_CASE( 0x1f )
        I8008_CASE( 0x20 ) I8008_CASE( 0x21 ) I8008_CASE( 0x22 ) I8008_CASE( 0x23 ) I8008_CASE( 0x24 ) I8008_CASE( 0x25 ) I8008_CASE( 0x26 ) I8008_CASE( 0x27 )
        I8008_CASE( 0x28 ) I8008_CASE( 0x29 ) I8008_CASE( 0x2a ) I8008_CASE( 0x2b ) I8008_CASE( 0x2c ) I8008_CASE( 0x2d ) I8008_CASE( 0x2e ) I8008_CASE( 0x2f )
        I8008_CASE( 0x30 ) I8008_CASE( 0x31 ) I8008_CASE( 0x32 ) I8008_CASE( 0x33 ) I8008_CASE( 0x34 ) I8008_CASE( 0x35 ) I8008_CASE( 0x36 ) I8008_CASE( 0x37 )
        I8008_CASE( 0x38 ) I8008_CASE( 0x39 ) I8008_CASE( 0x3a ) I8008_CASE( 0x3b ) I8008_CASE( 0x3c ) I8008_CASE( 0x3d ) I8008_CASE( 0x3e ) I8008_CASE( 0x3f )
        I8008_CASE( 0x40 ) I8008_CASE( 0x41 ) I8008_CASE( 0x42 ) I8008_CASE( 0x43 ) I8008_CASE( 0x44 ) I8008_CASE( 0x45 ) I8008_CASE( 0x46 ) I8008_CASE( 0x47 )
        I8008_CASE( 0x48 ) I8008_CASE( 0x49 ) I8008_CASE( 0x4a ) I8008_CASE( 0x4b ) I8008_CASE( 0x4c ) I8008_CASE( 0x4d ) I8008_CASE( 0x4e ) I8008_CASE( 0x4f )
        I8008_CASE( 0x50 ) I8008_CASE( 0x51 ) I8008_CASE( 0x52 ) I8008_CASE( 0x53 ) I8008_CASE( 0x54 ) I8008_CASE( 0x55 ) I8008_CASE( 0x56 ) I8008_CASE( 0x57 )
        I8008_CASE( 0x58 ) I8008_CASE( 0x59 ) I8008_CASE( 0x5a ) I8008_CASE( 0x5b ) I8008_CASE( 0x5c ) I8008_CASE( 0x5d ) I8008_CASE( 0x5e ) I8008_CASE( 0x5f )
        I8008_CASE( 0x60 ) I8008_CASE( 0x61 ) I8008_CASE( 0x62 ) I8008_CASE( 0x63 ) I8008_CASE( 0x64 ) I8008_CASE( 0x65 ) I8008_CASE( 0x66 ) I8008_CASE( 0x67 )
        I8008_CASE( 0x68 ) I8008_CASE( 0x69 ) I8008_CASE( 0x6a ) I8008_CASE( 0x6b ) I8008_CASE( 0x6c ) I8008_CASE( 0x6d ) I8008_CASE( 0x6e ) I8008_CASE( 0x6f )
        I8008_CASE( 0x70 ) I8008_CASE( 0x71 ) I8008_CASE( 0x72 ) I8008_CASE( 0x73 ) I8008_CASE( 0x74 ) I8008_CASE( 0x75 ) I8008_CASE( 0x76 ) I8008_CASE( 0x77 )
        I8008_CASE( 0x78 ) I8008_CASE( 0x79 ) I8008_CASE( 0x7a ) I8008_CASE( 0x7b ) I8008_CASE( 0x7c ) I8008_CASE( 0x7d ) I8008_CASE( 0x7e ) I8008_CASE( 0x7f )
        I8008_CASE( 0x80 ) I8008_CASE( 0x81 ) I8008_CASE( 0x82 ) I8008_CASE( 0x83 ) I8008_CASE( 0x84 ) I8008_CASE( 0x85 ) I8008_CASE( 0x86 ) I8008_CASE( 0x87 )
        I8008_CASE( 0x88 ) I8008_CASE( 0x89 ) I8008_CASE( 0x8a ) I8008_CASE( 0x8b ) I8008_CASE( 0x8c ) I8008_CASE( 0x8d ) I8008_CASE( 0x8e ) I8008_CASE( 0x8f )
        I8008_CASE( 0x90 ) I8008_CASE( 0x91 ) I8008_CASE( 0x92 ) I8008_CASE( 0x93 ) I8008_CASE( 0x94 ) I8008_CASE( 0x95 ) I8008_CASE( 0x96 ) I8008_CASE( 0x97 )
        I8008_CASE( 0x98 ) I8008_CASE( 0x99 ) I8008_CASE( 0x9a ) I8008_CASE( 0x9b ) I8008_CASE( 0x9c ) I8008_CASE( 0x9d ) I8008_CASE( 0x9e ) I8008_CASE( 0x9f )
        I8008_CASE( 0xa0 ) I8008_CASE( 0xa1 ) I8008_CASE( 0xa2 ) I8008_CASE( 0xa3 ) I8008_CASE( 0xa4 ) I8008_CASE( 0xa5 ) I8008_CASE( 0xa6 ) I8008_CASE( 0xa7 )
        I8008_CASE( 0xa8 ) I8008_CASE( 0xa9 ) I8008_CASE( 0xaa ) I8008_CASE( 0xab ) I8008_CASE( 0xac ) I8008_CASE( 0xad ) I8008_CASE( 0xae ) I8008_CASE( 0xaf )
        I8008_CASE( 0xb0 ) I8008_CASE( 0xb1 ) I8008_CASE( 0xb2 ) I8008_CASE( 0xb3 ) I8008_CASE( 0xb4 ) I8008_CASE( 0xb5 ) I8008_CASE( 0xb6 ) I8008_CASE( 0xb7 )
        I8008_CASE( 0xb8 ) I8008_CASE( 0xb9 ) I8008_CASE( 0xba ) I8008_CASE( 0xbb ) I8008_CASE( 0xbc ) I8008_CASE( 0xbd ) I8008_CASE( 0xbe ) I8008_CASE( 0xbf )
        I8008_CASE( 0xc0 ) I8008_CASE( 0xc1 ) I8008_CASE( 0xc2 ) I8008_CASE( 0xc3 ) I8008_CASE( 0xc4 ) I8008_CASE( 0xc5 ) I8008_CASE( 0xc6 ) I8008_CASE( 0xc7 )
        I8008_CASE( 0xc8 ) I8008_CASE( 0xc9 ) I8008_CASE( 0xca ) I8008_CASE( 0xcb ) I8008_CASE( 0xcc ) I8008_CASE( 0xcd ) I8008_CASE( 0xce ) I8008_CASE( 0xcf )
        I8008_CASE( 0xd0 ) I8008_CASE( 0xd1 ) I8008_CASE( 0xd2 ) I8008_CASE( 0xd3 ) I8008_CASE( 0xd4 ) I8008_CASE( 0xd5 ) I8008_CASE( 0xd6 ) I8008_CASE( 0xd7 )
        I8008_CASE( 0xd8 ) I8008_CASE( 0xd9 ) I8008_CASE( 0xda ) I8008_CASE( 0xdb ) I8008_CASE( 0xdc ) I8008_CASE( 0xdd ) I8008_CASE( 0xde ) I8008_CASE( 0xdf )
        I8008_CASE( 0xe0 ) I8008_CASE( 0xe1 ) I8008_CASE( 0xe2 ) I8008_CASE( 0xe3 ) I8008_CASE( 0xe4 ) I8008_CASE( 0xe5 ) I8008_CASE( 0xe6 ) I8008_CASE( 0xe7 )
        I8008_CASE( 0xe8 ) I8008_CASE( 0xe9 ) I8008_CASE( 0xea ) I8008_CASE( 0xeb ) I8008_CASE( 0xec ) I8008_CASE( 0xed ) I8008_CASE( 0xee ) I8008_CASE( 0xef )
        I8008_CASE( 0xf0 ) I8008_CASE( 0xf1 ) I8008_CASE( 0xf2 ) I8008_CASE( 0xf3 ) I8008_CASE( 0xf4 ) I8008_CASE( 0xf5 ) I8008_CASE( 0xf6 ) I8008_CASE( 0xf7 )
        I8008_CASE( 0xf8 ) I8008_CASE( 0xf9 ) I8008_CASE( 0xfa ) I8008_CASE( 0xfb ) I8008_CASE( 0xfc ) I8008_CASE( 0xfd ) I8008_CASE( 0xfe ) I8008_CASE( 0xff )
#undef I8008_CASE
    }
    unsigned clocks = states * 2;
    cycles += clocks;
    if ( m_tracer && ( halted || invalid ) )
        m_tracer->Trace( "%s at %04x, %llu cycles\n", invalid ? "undefined opcode" : "halt",
                         instructionAddress, (unsigned long long) cycles );
    return clocks;
} //execute

unsigned I8008::step()
{
    sync_state();
    return execute();
} //step

unsigned I8008::interrupt( uint8_t instruction )
{
    halted = ended = false;
    m_state &= stateTrace;
    return execute( instruction, true );
} //interrupt

uint64_t I8008::emulate( uint64_t maxcycles )
{
    sync_state();
    uint64_t start = cycles;
    uint64_t limit = start + maxcycles;
    // A final instruction can overshoot by up to 21 clocks. Only the rare
    // counter-wrap case needs subtraction inside the loop.
    if ( limit < start || limit > UINT64_MAX - 21 )
    {
        while ( cycles - start < maxcycles )
            if ( !execute() )
                break;
    }
    else
    {
        while ( cycles < limit )
            if ( !execute() )
                break;
    }
    return cycles - start;
} //emulate

const char * I8008::render_operation( uint16_t address ) const
{
    return render_operation( memory[ address & 0x3fff ], ( address + 1 ) & 0x3fff );
} //render_operation

const char * I8008::render_operation( uint8_t op, uint16_t operands ) const
{
    static char text[ 32 ];
    static const char regs[] = "ABCDEHLM";
    static const char * math[] = { "AD", "AC", "SU", "SB", "ND", "XR", "OR", "CP" };
    static const char * rotates[] = { "RLC", "RRC", "RAL", "RAR" };
    static const char flags[] = "CZSP";
    unsigned d = ( op >> 3 ) & 7, s = op & 7;
    unsigned value = memory[ operands & 0x3fff ];
    unsigned target = ( value | ( memory[ ( operands + 1 ) & 0x3fff ] << 8 ) ) & 0x3fff;
    if ( 0 == op || 1 == op || 255 == op )
        snprintf( text, sizeof( text ), "HLT" );
    else if ( op >= 0xc0 )
        snprintf( text, sizeof( text ), "L%c%c", regs[ d ], regs[ s ] );
    else if ( op >= 0x80 )
        snprintf( text, sizeof( text ), "%s%c", math[ d ], regs[ s ] );
    else if ( op >= 0x40 )
    {
        if ( op & 1 )
            snprintf( text, sizeof( text ), "%s %u", op < 0x51 ? "INP" : "OUT", ( op >> 1 ) & 31 );
        else if ( op & 4 )
            snprintf( text, sizeof( text ), "%s %04x", op & 2 ? "CAL" : "JMP", target );
        else
            snprintf( text, sizeof( text ), "%c%c%c %04x", op & 2 ? 'C' : 'J',
                      op & 0x20 ? 'T' : 'F', flags[ d & 3 ], target );
    }
    else
    {
        switch ( s )
        {
            case 0: case 1:
                if ( d > 0 && d < 7 )
                    snprintf( text, sizeof( text ), "%s%c", s ? "DC" : "IN", regs[ d ] );
                else
                    snprintf( text, sizeof( text ), "undefined" );
                break;
            case 2: snprintf( text, sizeof( text ), "%s", d < 4 ? rotates[ d ] : "undefined" ); break;
            case 3: snprintf( text, sizeof( text ), "R%c%c", op & 0x20 ? 'T' : 'F', flags[ d & 3 ] ); break;
            case 4: snprintf( text, sizeof( text ), "%sI %02x", math[ d ], value ); break;
            case 5: snprintf( text, sizeof( text ), "RST %u", d ); break;
            case 6: snprintf( text, sizeof( text ), "L%cI %02x", regs[ d ], value ); break;
            case 7: snprintf( text, sizeof( text ), "RET" ); break;
        }
    }
    return text;
} //render_operation

void I8008::trace_state() const
{
    trace_state( pc(), memory[ pc() ], false );
} //trace_state

void I8008::trace_state( uint16_t address, uint8_t op, bool injected ) const
{
    if ( !m_tracer || !m_tracer->IsEnabled() )
        return;
    if ( m_symbolLookup )
    {
        uint16_t offset = 0;
        const char * name = m_symbolLookup( address, offset );
        if ( name != m_previousSymbol && name )
        {
            if ( offset ) m_tracer->Trace( "%s + %x:\n", name, offset );
            else m_tracer->Trace( "%s:\n", name );
        }
        m_previousSymbol = name;
    }
    uint16_t operands = ( address + ( injected ? 0 : 1 ) ) & 0x3fff;
    m_tracer->Trace( "pc %04x, op %02x, op2 %02x, op3 %02x, a %02x, b %02x, c %02x, d %02x, e %02x, h %02x, l %02x, sp %u, %c%c%c%c, cycles %llu, %s%s\n",
                     address, op, memory[ operands ], memory[ ( operands + 1 ) & 0x3fff ],
                     r[ 0 ], r[ 1 ], r[ 2 ], r[ 3 ], r[ 4 ], r[ 5 ], r[ 6 ], sp,
                     fCarry ? 'C' : 'c', fZero ? 'Z' : 'z', fSign ? 'S' : 's', fParity ? 'P' : 'p',
                     (unsigned long long) cycles, injected ? "interrupt: " : "", render_operation( op, operands ) );
} //trace_state
