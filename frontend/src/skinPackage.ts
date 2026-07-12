import { strFromU8, unzipSync } from 'fflate'
import { OFFICIAL_SKIN_PUBLIC_KEYS } from './officialSkinKeys'
import {
  CUSTOM_SKIN_MANIFEST_MAX_BYTES,
  isSafeSkinAssetPath,
  isV3Skin,
  parseDeclarativeSkin,
  skinAssetMime,
  type DeclarativeSkin,
  type SkinAssetDescriptor,
  type V3DeclarativeSkin
} from './skinProtocol'

export const SKIN_PACKAGE_MAX_COMPRESSED_BYTES = 32 * 1024 * 1024
export const SKIN_PACKAGE_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
export const SKIN_PACKAGE_MAX_ENTRIES = 96
export const SKIN_SIGNATURE_SCHEMA = 'workmode-skin-signature/v1'

const IMAGE_MAX_BYTES = 16 * 1024 * 1024
const ICON_MAX_BYTES = 2 * 1024 * 1024
const FONT_MAX_BYTES = 8 * 1024 * 1024
const STYLESHEET_MAX_BYTES = 512 * 1024
const SIGNATURE_MAX_BYTES = 64 * 1024
const ZIP_LOCAL_FILE = 0x04034b50
const ZIP_CENTRAL_FILE = 0x02014b50
const ZIP_END = 0x06054b50

export interface ParsedSkinPackage {
  skin: V3DeclarativeSkin
  assets: Map<string, Blob>
  styles: { layout: Blob; visual: Blob }
  trust: OfficialSkinTrust
}

export type ParsedSkinImport = ParsedSkinPackage

export interface OfficialSkinTrust {
  keyId: string
  packageDigest: string
}

export type OfficialSkinPublicKeys = Readonly<Record<string, string>>

export interface SkinSignedFile {
  path: string
  size: number
  sha256: string
}

export interface SkinSignatureEnvelope {
  schema: typeof SKIN_SIGNATURE_SCHEMA
  keyId: string
  algorithm: 'Ed25519'
  files: SkinSignedFile[]
  signature: string
}

type UnsignedSkinSignatureEnvelope = Omit<SkinSignatureEnvelope, 'signature'>

interface ZipEntryMetadata {
  path: string
  compressedSize: number
  uncompressedSize: number
  directory: boolean
}

function findEndOfCentralDirectory(view: DataView) {
  const earliest = Math.max(0, view.byteLength - 65557)
  for (let offset = view.byteLength - 22; offset >= earliest; offset -= 1) {
    if (view.getUint32(offset, true) === ZIP_END) return offset
  }
  throw new Error('皮肤包不是有效 ZIP：缺少中央目录')
}

function inspectZipArchive(bytes: Uint8Array): ZipEntryMetadata[] {
  if (bytes.byteLength < 22 || new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(0, true) !== ZIP_LOCAL_FILE) {
    throw new Error('皮肤包不是有效 ZIP')
  }
  if (bytes.byteLength > SKIN_PACKAGE_MAX_COMPRESSED_BYTES) throw new Error('皮肤包压缩后不能超过 32 MB')
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const end = findEndOfCentralDirectory(view)
  if (view.getUint16(end + 4, true) !== 0 || view.getUint16(end + 6, true) !== 0) {
    throw new Error('皮肤包不支持分卷 ZIP')
  }
  const entryCount = view.getUint16(end + 10, true)
  const centralSize = view.getUint32(end + 12, true)
  const centralOffset = view.getUint32(end + 16, true)
  if (!entryCount || entryCount > SKIN_PACKAGE_MAX_ENTRIES) throw new Error(`皮肤包条目数必须在 1-${SKIN_PACKAGE_MAX_ENTRIES} 之间`)
  if (centralOffset + centralSize > end || centralOffset >= bytes.byteLength) throw new Error('皮肤包中央目录越界')

  const decoder = new TextDecoder('utf-8', { fatal: true })
  const paths = new Set<string>()
  const entries: ZipEntryMetadata[] = []
  let total = 0
  let offset = centralOffset
  for (let index = 0; index < entryCount; index += 1) {
    if (offset + 46 > bytes.byteLength || view.getUint32(offset, true) !== ZIP_CENTRAL_FILE) {
      throw new Error('皮肤包中央目录损坏')
    }
    const flags = view.getUint16(offset + 8, true)
    const method = view.getUint16(offset + 10, true)
    const compressedSize = view.getUint32(offset + 20, true)
    const uncompressedSize = view.getUint32(offset + 24, true)
    const nameLength = view.getUint16(offset + 28, true)
    const extraLength = view.getUint16(offset + 30, true)
    const commentLength = view.getUint16(offset + 32, true)
    const next = offset + 46 + nameLength + extraLength + commentLength
    if (!nameLength || next > bytes.byteLength) throw new Error('皮肤包条目名称损坏')
    if ((flags & 1) !== 0) throw new Error('皮肤包不能包含加密条目')
    if (method !== 0 && method !== 8) throw new Error('皮肤包只支持 stored 或 deflate 压缩')
    if (compressedSize === 0xffffffff || uncompressedSize === 0xffffffff) throw new Error('皮肤包暂不支持 ZIP64')
    const path = decoder.decode(bytes.subarray(offset + 46, offset + 46 + nameLength))
    const directory = path.endsWith('/')
    const validatedPath = directory ? path.slice(0, -1) : path
    if (!isSafeSkinAssetPath(validatedPath) || (directory && uncompressedSize !== 0)) {
      throw new Error(`皮肤包包含不安全路径：${path}`)
    }
    const key = path.toLowerCase()
    if (paths.has(key)) throw new Error(`皮肤包包含重复路径：${path}`)
    paths.add(key)
    total += uncompressedSize
    if (total > SKIN_PACKAGE_MAX_UNCOMPRESSED_BYTES) throw new Error('皮肤包解压后不能超过 64 MB')
    entries.push({ path, compressedSize, uncompressedSize, directory })
    offset = next
  }
  return entries
}

function hasPrefix(bytes: Uint8Array, prefix: number[]) {
  return prefix.every((value, index) => bytes[index] === value)
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function bytesToHex(bytes: Uint8Array) {
  return Array.from(bytes, (value) => value.toString(16).padStart(2, '0')).join('')
}

async function sha256(bytes: Uint8Array) {
  if (!globalThis.crypto?.subtle) throw new Error('当前环境不支持官方皮肤验签')
  return new Uint8Array(await crypto.subtle.digest('SHA-256', bytes as BufferSource))
}

function decodeBase64(value: string, label: string) {
  if (!value || value.length > 512 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) throw new Error(`${label}不是有效 Base64`)
  try {
    return Uint8Array.from(atob(value), (character) => character.charCodeAt(0))
  } catch {
    throw new Error(`${label}不是有效 Base64`)
  }
}

export function canonicalSkinSignaturePayload(envelope: UnsignedSkinSignatureEnvelope) {
  return new TextEncoder().encode(JSON.stringify({
    schema: envelope.schema,
    keyId: envelope.keyId,
    algorithm: envelope.algorithm,
    files: envelope.files.map((file) => ({ path: file.path, size: file.size, sha256: file.sha256 }))
  }))
}

function parseSignatureEnvelope(bytes: Uint8Array): SkinSignatureEnvelope {
  if (!bytes.byteLength || bytes.byteLength > SIGNATURE_MAX_BYTES) throw new Error('皮肤包官方签名文件大小异常')
  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
  } catch {
    throw new Error('皮肤包官方签名文件损坏')
  }
  if (!isObject(parsed) || parsed.schema !== SKIN_SIGNATURE_SCHEMA || parsed.algorithm !== 'Ed25519') {
    throw new Error('皮肤包缺少受支持的官方签名')
  }
  if (typeof parsed.keyId !== 'string' || !/^[A-Za-z0-9._-]{1,64}$/.test(parsed.keyId)) throw new Error('皮肤包签名 keyId 无效')
  if (typeof parsed.signature !== 'string') throw new Error('皮肤包官方签名缺失')
  if (!Array.isArray(parsed.files) || parsed.files.length < 3 || parsed.files.length > SKIN_PACKAGE_MAX_ENTRIES - 1) {
    throw new Error('皮肤包签名文件清单数量异常')
  }
  const paths = new Set<string>()
  const files = parsed.files.map((candidate, index): SkinSignedFile => {
    if (!isObject(candidate) || typeof candidate.path !== 'string' || !isSafeSkinAssetPath(candidate.path)
      || candidate.path === 'signature.json') throw new Error(`皮肤包签名文件清单第 ${index + 1} 项路径无效`)
    if (!Number.isSafeInteger(candidate.size) || Number(candidate.size) < 0) throw new Error(`皮肤包签名文件 ${candidate.path} 大小无效`)
    if (typeof candidate.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(candidate.sha256)) {
      throw new Error(`皮肤包签名文件 ${candidate.path} 摘要无效`)
    }
    const normalized = candidate.path.toLowerCase()
    if (paths.has(normalized)) throw new Error(`皮肤包签名文件清单包含重复路径：${candidate.path}`)
    paths.add(normalized)
    return { path: candidate.path, size: Number(candidate.size), sha256: candidate.sha256 }
  })
  const sorted = [...files].sort((left, right) => left.path < right.path ? -1 : left.path > right.path ? 1 : 0)
  if (files.some((file, index) => file.path !== sorted[index].path)) throw new Error('皮肤包签名文件清单必须按路径排序')
  return {
    schema: SKIN_SIGNATURE_SCHEMA,
    keyId: parsed.keyId,
    algorithm: 'Ed25519',
    files,
    signature: parsed.signature
  }
}

async function verifyOfficialSignature(
  envelope: SkinSignatureEnvelope,
  files: Record<string, Uint8Array>,
  publicKeys: OfficialSkinPublicKeys
) {
  const publicKeyText = publicKeys[envelope.keyId]
  if (!publicKeyText) throw new Error(`皮肤包签名者 ${envelope.keyId} 不受信任`)
  const archivePaths = Object.keys(files).filter((path) => path !== 'signature.json' && !path.endsWith('/')).sort()
  const signedPaths = envelope.files.map((file) => file.path)
  if (archivePaths.length !== signedPaths.length || archivePaths.some((path, index) => path !== signedPaths[index])) {
    throw new Error('皮肤包内容与官方签名文件清单不一致')
  }
  for (const descriptor of envelope.files) {
    const bytes = files[descriptor.path]
    if (!bytes || bytes.byteLength !== descriptor.size) throw new Error(`皮肤包签名文件 ${descriptor.path} 大小不一致`)
    if (bytesToHex(await sha256(bytes)) !== descriptor.sha256) throw new Error(`皮肤包签名文件 ${descriptor.path} 摘要不一致`)
  }
  const publicKeyBytes = decodeBase64(publicKeyText, '官方皮肤公钥')
  const signatureBytes = decodeBase64(envelope.signature, '皮肤包签名')
  if (publicKeyBytes.byteLength !== 32 || signatureBytes.byteLength !== 64) throw new Error('皮肤包官方签名长度无效')
  let publicKey: CryptoKey
  try {
    publicKey = await crypto.subtle.importKey('raw', publicKeyBytes, 'Ed25519', false, ['verify'])
  } catch {
    throw new Error('无法载入官方皮肤公钥')
  }
  const valid = await crypto.subtle.verify(
    'Ed25519',
    publicKey,
    signatureBytes as BufferSource,
    canonicalSkinSignaturePayload(envelope) as BufferSource
  )
  if (!valid) throw new Error('皮肤包官方签名验证失败')
}

function validateMagic(bytes: Uint8Array, descriptor: SkinAssetDescriptor) {
  const mime = skinAssetMime(descriptor)
  const valid = mime === 'image/png'
    ? hasPrefix(bytes, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
    : mime === 'image/jpeg'
      ? hasPrefix(bytes, [0xff, 0xd8, 0xff])
      : mime === 'image/webp'
        ? hasPrefix(bytes, [0x52, 0x49, 0x46, 0x46]) && bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
        : mime === 'font/woff2'
          ? hasPrefix(bytes, [0x77, 0x4f, 0x46, 0x32])
          : false
  if (!valid) throw new Error(`资源 ${descriptor.path} 的文件签名与声明格式不匹配`)
  return mime as string
}

function validateAssetSize(bytes: Uint8Array, descriptor: SkinAssetDescriptor) {
  const limit = descriptor.kind === 'font' ? FONT_MAX_BYTES : descriptor.kind === 'icon' ? ICON_MAX_BYTES : IMAGE_MAX_BYTES
  if (!bytes.byteLength || bytes.byteLength > limit) throw new Error(`资源 ${descriptor.path} 大小超出允许范围`)
}

export async function parseSkinPackageBytes(
  input: Uint8Array,
  publicKeys: OfficialSkinPublicKeys = OFFICIAL_SKIN_PUBLIC_KEYS
): Promise<ParsedSkinPackage> {
  const metadata = inspectZipArchive(input)
  const files = unzipSync(input)
  const extractedPaths = Object.keys(files)
  if (extractedPaths.length !== metadata.length) throw new Error('皮肤包条目数量与中央目录不一致')
  metadata.forEach((entry) => {
    const data = files[entry.path]
    if (!data || data.byteLength !== entry.uncompressedSize) throw new Error(`皮肤包条目大小不一致：${entry.path}`)
  })
  const signatureBytes = files['signature.json']
  if (!signatureBytes) throw new Error('皮肤包缺少官方签名 signature.json')
  const signature = parseSignatureEnvelope(signatureBytes)
  await verifyOfficialSignature(signature, files, publicKeys)

  const manifestBytes = files['manifest.json']
  if (!manifestBytes) throw new Error('皮肤包根目录缺少 manifest.json')
  if (manifestBytes.byteLength > CUSTOM_SKIN_MANIFEST_MAX_BYTES) throw new Error('manifest.json 不能超过 256 KB')
  const skin = parseDeclarativeSkin(strFromU8(manifestBytes))
  if (!isV3Skin(skin)) throw new Error('压缩皮肤包只支持 workmode-skin/v3')

  const layoutBytes = files['layout.css']
  const visualBytes = files['visual.css']
  if (!layoutBytes || !visualBytes) throw new Error('官方皮肤包必须同时包含 layout.css 和 visual.css')
  if (!layoutBytes.byteLength || layoutBytes.byteLength > STYLESHEET_MAX_BYTES
    || !visualBytes.byteLength || visualBytes.byteLength > STYLESHEET_MAX_BYTES) {
    throw new Error('官方皮肤 CSS 单文件大小必须在 1 B 到 512 KB 之间')
  }
  try {
    new TextDecoder('utf-8', { fatal: true }).decode(layoutBytes)
    new TextDecoder('utf-8', { fatal: true }).decode(visualBytes)
  } catch {
    throw new Error('官方皮肤 CSS 必须是有效 UTF-8 文本')
  }

  const allowedPaths = new Set(['manifest.json', 'signature.json', 'layout.css', 'visual.css', 'LICENSE.txt', ...skin.assets.map((asset) => asset.path)])
  const directoryPaths = new Set(metadata.filter((entry) => entry.directory).map((entry) => entry.path))
  const undeclared = extractedPaths.filter((path) => !directoryPaths.has(path) && !allowedPaths.has(path))
  if (undeclared.length) throw new Error(`皮肤包包含未声明文件：${undeclared.join(', ')}`)
  const missing = skin.assets.filter((asset) => !files[asset.path])
  if (missing.length) throw new Error(`皮肤包缺少资源：${missing.map((asset) => asset.path).join(', ')}`)

  const assets = new Map<string, Blob>()
  skin.assets.forEach((descriptor) => {
    const bytes = files[descriptor.path]
    validateAssetSize(bytes, descriptor)
    const mime = validateMagic(bytes, descriptor)
    assets.set(descriptor.id, new Blob([bytes.slice().buffer], { type: mime }))
  })
  return {
    skin,
    assets,
    styles: {
      layout: new Blob([layoutBytes.slice().buffer], { type: 'text/css' }),
      visual: new Blob([visualBytes.slice().buffer], { type: 'text/css' })
    },
    trust: {
      keyId: signature.keyId,
      packageDigest: bytesToHex(await sha256(input))
    }
  }
}

export async function parseSkinImportFile(
  file: File,
  publicKeys: OfficialSkinPublicKeys = OFFICIAL_SKIN_PUBLIC_KEYS
): Promise<ParsedSkinImport> {
  if (!file.name.toLowerCase().endsWith('.workmode-skin')) {
    throw new Error(`「${file.name}」只接受官方签名的 .workmode-skin 文件`)
  }
  if (file.size > SKIN_PACKAGE_MAX_COMPRESSED_BYTES) throw new Error(`「${file.name}」不能超过 32 MB`)
  return parseSkinPackageBytes(new Uint8Array(await file.arrayBuffer()), publicKeys)
}
