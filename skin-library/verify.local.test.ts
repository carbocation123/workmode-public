import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { parseSkinPackageBytes } from '../frontend/src/skinPackage'

const packages = [
  ['amethyst-observatory.workmode-skin', 'amethyst-observatory', '3.1.0'],
  ['cream-puff.workmode-skin', 'cream-puff-v3', '3.2.3'],
  ['cryo-gem-tech.workmode-skin', 'cryo-gem-tech', '3.1.0'],
  ['green-phosphor.workmode-skin', 'green-phosphor-terminal', '4.0.2'],
  ['midnight-console.workmode-skin', 'midnight-console', '3.1.0'],
  ['neon-ice.workmode-skin', 'neon-ice-v3', '3.1.0'],
  ['pixel-night-shift.workmode-skin', 'pixel-night-shift', '3.1.2']
] as const

describe('locally signed reward skin packages', () => {
  it.each(packages)('verifies %s with the embedded production key', async (filename, skinId, version) => {
    const bytes = new Uint8Array(readFileSync(new URL(`./packages/${filename}`, import.meta.url)))
    const parsed = await parseSkinPackageBytes(bytes)

    expect(parsed.skin.id).toBe(skinId)
    expect(parsed.skin.version).toBe(version)
    expect(parsed.trust.keyId).toBe('workmode-official-2026-01')
  })

  it('keeps both declared pixel fonts in the pixel night shift package', async () => {
    const bytes = new Uint8Array(readFileSync(new URL('./packages/pixel-night-shift.workmode-skin', import.meta.url)))
    const parsed = await parseSkinPackageBytes(bytes)

    expect(Array.from(parsed.assets.keys()).sort()).toEqual(['pixel-mono', 'pixel-proportional'])
    expect(await parsed.styles.visual.text()).toContain('--pixel-magenta: #ff4fa3')
  })
})
