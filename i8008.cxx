// Intel 8008 emulator. All memory is RAM; no wait states.
// Timing: Intel 8008 Users Manual, November 1972, section IV.
// Each T state takes two clock periods. The stack includes the active PC.

#include <string.h>
#include "i8008.hxx"

uint8_t memory[ 16384 ];

// Keep the decoder in the bulk loop without duplicating its implementation.
#if defined( _MSC_VER )
#define I8008_FORCE_INLINE __forceinline
#elif defined( __GNUC__ ) || defined( __clang__ )
#define I8008_FORCE_INLINE inline __attribute__((always_inline))
#else
#define I8008_FORCE_INLINE inline
#endif

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

uint8_t I8008::fetch()
{
    uint8_t value = memory[ pc() ];
    stack[ sp ] = ( pc() + 1 ) & 0x3fff;
    return value;
} //fetch

void I8008::set_reg( unsigned n, uint8_t value )
{
    if ( 7 == n )
        memory[ address() ] = value;
    else
        r[ n ] = value;
} //set_reg

void I8008::set_szp( uint8_t value )
{
    fZero = ( 0 == value );
    fSign = ( 0 != ( value & 0x80 ) );
    value ^= value >> 4;
    value ^= value >> 2;
    value ^= value >> 1;
    fParity = ( 0 == ( value & 1 ) );
} //set_szp

bool I8008::condition( uint8_t op ) const
{
    // Pack C/Z/S/P in condition-code order, avoiding a temporary bool array
    // and its indexed stack access. Keep the public named flag fields intact.
    unsigned flags = unsigned( fCarry ) | ( unsigned( fZero ) << 1 ) |
                     ( unsigned( fSign ) << 2 ) | ( unsigned( fParity ) << 3 );
    return ( ( flags >> ( ( op >> 3 ) & 3 ) ) & 1 ) == ( ( op >> 5 ) & 1u );
} //condition

void I8008::alu( unsigned operation, uint8_t value )
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
                    r[ d ] += ( 0 == ( op & 1 ) ) ? 1 : -1;
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
