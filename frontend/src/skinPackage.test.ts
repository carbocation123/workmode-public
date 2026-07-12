import { strToU8, zipSync } from 'fflate'
import { describe, expect, it } from 'vitest'
import { CUSTOM_SKIN_SCHEMA } from './customSkin'
import {
  SKIN_SIGNATURE_SCHEMA,
  canonicalSkinSignaturePayload,
  parseSkinImportFile,
  parseSkinPackageBytes,
  type OfficialSkinPublicKeys,
  type SkinSignatureEnvelope
} from './skinPackage'

const manifest = {
  schema: CUSTOM_SKIN_SCHEMA,
  id: 'packed-amethyst',
  name: 'Packed Amethyst',
  version: '3.0.0',
  foundation: 'dark',
  palette: { accent: '#a766e8', background: '#090611', surface: '#160c23', text: '#e5d9ef' },
  typography: { preset: 'scholar', assets: { display: 'display-font' } },
  material: { preset: 'obsidian' },
  geometry: { lineWidth: 2 },
  components: { chrome: 'observatory', messages: 'manuscript', tools: 'ritual', context: 'dial', fileTree: 'archive' },
  icons: { preset: 'arcane', overrides: { folder: 'folder-icon' } },
  background: { asset: 'background', fit: 'cover', position: 'center', opacity: 0.4 },
  effects: { preset: 'stars', intensity: 0.4, motion: 'subtle' },
  decoration: {
    preset: 'arcane',
    density: 0.4,
    overlay: { asset: 'decoration-overlay', fit: 'contain', position: 'right', opacity: 0.32 }
  },
  assets: [
    { id: 'background', path: 'backgrounds/main.webp', kind: 'image' },
    { id: 'decoration-overlay', path: 'decorations/frame.png', kind: 'image' },
    { id: 'folder-icon', path: 'icons/folder.png', kind: 'icon' },
    { id: 'display-font', path: 'fonts/display.woff2', kind: 'font' }
  ]
}

const webp = new Uint8Array([0x52, 0x49, 0x46, 0x46, 0x04, 0, 0, 0, 0x57, 0x45, 0x42, 0x50])
const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
const woff2 = new Uint8Array([0x77, 0x4f, 0x46, 0x32, 0, 0, 0, 0])

function base64(bytes: Uint8Array) {
  return btoa(String.fromCharCode(...bytes))
}

function hex(bytes: Uint8Array) {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

async function sha256(bytes: Uint8Array) {
  return new Uint8Array(await crypto.subtle.digest('SHA-256', bytes as BufferSource))
}

async function signedPackage(
  overrides: Record<string, Uint8Array> = {},
  keyId = 'test-official-key'
): Promise<{ bytes: Uint8Array; keys: OfficialSkinPublicKeys; envelope: SkinSignatureEnvelope }> {
  const files: Record<string, Uint8Array> = {
    'manifest.json': strToU8(JSON.stringify(manifest)),
    'layout.css': strToU8('[data-skin-slot="app-shell"] { grid-template-columns: 48px 1fr; }'),
    'visual.css': strToU8('[data-skin-slot="message-stream"] { color: #a766e8; }'),
    'backgrounds/main.webp': webp,
    'decorations/frame.png': png,
    'icons/folder.png': png,
    'fonts/display.woff2': woff2,
    ...overrides
  }
  const keyPair = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify'])
  const publicKey = new Uint8Array(await crypto.subtle.exportKey('raw', keyPair.publicKey))
  const signedFiles = await Promise.all(Object.entries(files)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(async ([path, value]) => ({ path, size: value.byteLength, sha256: hex(await sha256(value)) })))
  const unsignedEnvelope = {
    schema: SKIN_SIGNATURE_SCHEMA as typeof SKIN_SIGNATURE_SCHEMA,
    keyId,
    algorithm: 'Ed25519' as const,
    files: signedFiles
  }
  const signature = new Uint8Array(await crypto.subtle.sign(
    'Ed25519',
    keyPair.privateKey,
    canonicalSkinSignaturePayload(unsignedEnvelope) as BufferSource
  ))
  const envelope: SkinSignatureEnvelope = { ...unsignedEnvelope, signature: base64(signature) }
  return {
    bytes: zipSync({ ...files, 'signature.json': strToU8(JSON.stringify(envelope)) }),
    keys: { [keyId]: base64(publicKey) },
    envelope
  }
}

describe('official signed skin packages', () => {
  it('verifies the whole package before loading CSS and declared local assets', async () => {
    const fixture = await signedPackage()
    const parsed = await parseSkinPackageBytes(fixture.bytes, fixture.keys)

    expect(parsed.skin.id).toBe('packed-amethyst')
    expect(parsed.trust.keyId).toBe('test-official-key')
    expect(parsed.trust.packageDigest).toMatch(/^[a-f0-9]{64}$/)
    expect(await parsed.styles.layout.text()).toContain('grid-template-columns')
    expect(await parsed.styles.visual.text()).toContain('message-stream')
    expect(Array.from(parsed.assets.keys())).toEqual(['background', 'decoration-overlay', 'folder-icon', 'display-font'])
    expect(parsed.assets.get('background')?.type).toBe('image/webp')
    expect(parsed.assets.get('display-font')?.type).toBe('font/woff2')
  })

  it('rejects missing signatures, unknown signers and any CSS modification', async () => {
    const fixture = await signedPackage()
    const unsigned = zipSync({
      'manifest.json': strToU8(JSON.stringify(manifest)),
      'layout.css': strToU8('body{}'),
      'visual.css': strToU8('body{}')
    })
    await expect(parseSkinPackageBytes(unsigned, fixture.keys)).rejects.toThrow('官方签名')
    await expect(parseSkinPackageBytes(fixture.bytes, {})).rejects.toThrow('不受信任')

    const envelopeBytes = strToU8(JSON.stringify(fixture.envelope))
    const tampered = zipSync({
      'manifest.json': strToU8(JSON.stringify(manifest)),
      'layout.css': strToU8('body { display: none; }'),
      'visual.css': strToU8('[data-skin-slot="message-stream"] { color: #a766e8; }'),
      'backgrounds/main.webp': webp,
      'decorations/frame.png': png,
      'icons/folder.png': png,
      'fonts/display.woff2': woff2,
      'signature.json': envelopeBytes
    })
    await expect(parseSkinPackageBytes(tampered, fixture.keys)).rejects.toThrow('不一致')
  })

  it('rejects zip traversal, undeclared files, mismatched magic and missing assets', async () => {
    const traversal = await signedPackage({ '../escape.png': png })
    await expect(parseSkinPackageBytes(traversal.bytes, traversal.keys)).rejects.toThrow('不安全路径')

    const undeclared = await signedPackage({ 'icons/hidden.png': png })
    await expect(parseSkinPackageBytes(undeclared.bytes, undeclared.keys)).rejects.toThrow('未声明')

    const badMagic = await signedPackage({ 'backgrounds/main.webp': strToU8('<script>bad</script>') })
    await expect(parseSkinPackageBytes(badMagic.bytes, badMagic.keys)).rejects.toThrow('文件签名')

    const missing = await signedPackage({ 'backgrounds/main.webp': new Uint8Array() })
    await expect(parseSkinPackageBytes(missing.bytes, missing.keys)).rejects.toThrow('大小')
  })

  it('accepts only .workmode-skin files and never imports legacy JSON', async () => {
    const fixture = await signedPackage()
    await expect(parseSkinImportFile(
      new File([fixture.bytes as BlobPart], 'official.workmode-skin'),
      fixture.keys
    )).resolves.toMatchObject({ skin: { id: 'packed-amethyst' } })
    await expect(parseSkinImportFile(
      new File([JSON.stringify(manifest)], 'legacy.workmode-skin.json'),
      fixture.keys
    )).rejects.toThrow('只接受官方签名')
  })
})
