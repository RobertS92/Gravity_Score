import { describe, expect, it } from 'vitest'
import { parseStructuredCommand } from './commandParser'

describe('parseStructuredCommand CSC athlete selection', () => {
  it('parses quoted score --athlete', () => {
    expect(parseStructuredCommand('score --athlete "Arch Manning"')).toEqual({
      kind: 'score',
      name: 'Arch Manning',
    })
  })

  it('parses unquoted score --athlete', () => {
    expect(parseStructuredCommand('score --athlete Arch Manning')).toEqual({
      kind: 'score',
      name: 'Arch Manning',
    })
  })

  it('parses csc --athlete', () => {
    expect(parseStructuredCommand('csc --athlete "Arch Manning"')).toEqual({
      kind: 'csc_report',
      name: 'Arch Manning',
    })
  })

  it('parses csc --report --athlete', () => {
    expect(parseStructuredCommand('csc --report --athlete "Arch Manning"')).toEqual({
      kind: 'csc_report',
      name: 'Arch Manning',
    })
  })

  it('parses csc --report without an athlete', () => {
    expect(parseStructuredCommand('csc --report')).toEqual({ kind: 'csc_report' })
  })
})
