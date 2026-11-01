#pragma once
#include <stdint.h>
#include "trace.hxx"

extern uint8_t memory[ 16384 ];
extern uint8_t i8008_input( uint8_t port );
extern void i8008_output( uint8_t port, uint8_t value );

struct I8008
{
    uint8_t r[ 7 ]; // A, B, C, D, E, H, L
    uint16_t stack[ 8 ]; // the selected register is the program counter
    uint8_t sp;
    bool fCarry, fZero, fSign, fParity;
    bool halted, ended, invalid;
    uint64_t cycles;

    void set_tracer( CTrace * tracer ) { m_tracer = tracer; } // caller owns the tracer
    void trace_instructions( bool trace ) { if ( trace ) m_state |= stateTrace; else m_state &= ~stateTrace; }
    void trace_state() const;
    void set_symbol_lookup( const char * (*lookup)( uint16_t, uint16_t & ) ) { m_symbolLookup = lookup; m_previousSymbol = 0; }
    const char * render_operation( uint16_t address ) const;

    void power_on( uint16_t address = 0 );
    uint16_t pc() const { return stack[ sp ]; }
    void end_emulation() { ended = true; m_state |= stateEnded; }
    uint64_t emulate( uint64_t maxcycles ); // finishes the last instruction; clock periods, not T states
    unsigned step();
    unsigned interrupt( uint8_t instruction ); // injected opcode; operands still fetched from RAM

private:
    CTrace * m_tracer = 0;
    const char * (*m_symbolLookup)( uint16_t, uint16_t & ) = 0;
    mutable const char * m_previousSymbol = 0;
    enum { stateHalted = 1, stateEnded = 2, stateTrace = 4 };
    unsigned m_state = 0;
    void sync_state() // preserve direct writes to the public stop fields between calls
    {
        m_state = ( m_state & stateTrace ) | ( halted ? stateHalted : 0 ) | ( ended ? stateEnded : 0 );
    }
    void trace_state( uint16_t address, uint8_t op, bool injected ) const;
    const char * render_operation( uint8_t op, uint16_t operands ) const;
    uint8_t fetch();
    uint16_t address() const { return ( ( r[ 5 ] << 8 ) | r[ 6 ] ) & 0x3fff; }
    uint8_t get_reg( unsigned n ) const { return ( 7 == n ) ? memory[ address() ] : r[ n ]; }
    void set_reg( unsigned n, uint8_t value );
    void set_szp( uint8_t value );
    bool condition( uint8_t op ) const;
    void alu( unsigned operation, uint8_t value );
    unsigned execute( uint8_t op = 0, bool injected = false );
};
