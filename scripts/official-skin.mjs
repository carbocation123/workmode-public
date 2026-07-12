import { createHash, createPrivateKey, createPublicKey, generateKeyPairSync, sign } from 'node:crypto'
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { strToU8, zipSync } from '../frontend/node_modules/fflate/esm/index.mjs'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SECRET = join(ROOT, '.release-secrets', 'official-skin-ed25519.pem')
const PUBLIC_SOURCE = join(ROOT, 'frontend', 'src', 'officialSkinKeys.ts')
const KEY_ID = 'workmode-official-2026-01'
const SIGNATURE_SCHEMA = 'workmode-skin-signature/v1'

function usage() {
  throw new Error('Usage: node scripts/official-skin.mjs init | sign <source-directory> <output.workmode-skin>')
}

function base64UrlToBase64(value) {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/')
  return padded + '='.repeat((4 - padded.length % 4) % 4)
}

function publicKeyBase64(privatePem) {
  const publicJwk = createPublicKey(createPrivateKey(privatePem)).export({ format: 'jwk' })
  if (!publicJwk.x) throw new Error('Could not export Ed25519 public key')
  return base64UrlToBase64(publicJwk.x)
}

function ensureKey() {
  mkdirSync(dirname(SECRET), { recursive: true })
  if (!existsSync(SECRET)) {
    const pair = generateKeyPairSync('ed25519')
    writeFileSync(SECRET, pair.privateKey.export({ format: 'pem', type: 'pkcs8' }), { mode: 0o600 })
  }
  const privatePem = readFileSync(SECRET, 'utf8')
  const publicKey = publicKeyBase64(privatePem)
  const source = `// Public verification keys for official Workmode skin packages.\n// The matching private keys live only in .release-secrets / CI secrets.\nexport const OFFICIAL_SKIN_PUBLIC_KEYS: Readonly<Record<string, string>> = {\n  '${KEY_ID}': '${publicKey}'\n}\n`
  writeFileSync(PUBLIC_SOURCE, source, 'utf8')
  return { privatePem, publicKey }
}

function listFiles(root, current = root) {
  const output = []
  for (const name of readdirSync(current)) {
    if (name === 'signature.json') continue
    const full = join(current, name)
    const stat = lstatSync(full)
    if (stat.isSymbolicLink()) throw new Error(`Skin source cannot contain symlinks: ${full}`)
    if (stat.isDirectory()) output.push(...listFiles(root, full))
    else if (stat.isFile()) output.push(relative(root, full).split(sep).join('/'))
  }
  return output.sort((left, right) => left < right ? -1 : left > right ? 1 : 0)
}

function validatePath(path) {
  if (!path || path.startsWith('/') || path.includes('\\') || path.split('/').some((part) => !part || part === '.' || part === '..')) {
    throw new Error(`Unsafe skin package path: ${path}`)
  }
}

function canonicalPayload(envelope) {
  return Buffer.from(JSON.stringify({
    schema: envelope.schema,
    keyId: envelope.keyId,
    algorithm: envelope.algorithm,
    files: envelope.files.map((file) => ({ path: file.path, size: file.size, sha256: file.sha256 }))
  }), 'utf8')
}

function signPackage(sourceDirectory, outputFile) {
  const source = resolve(sourceDirectory)
  const output = resolve(outputFile)
  const required = ['manifest.json', 'layout.css', 'visual.css']
  const paths = listFiles(source)
  required.forEach((path) => {
    if (!paths.includes(path)) throw new Error(`Official skin source is missing ${path}`)
  })
  const files = {}
  const signedFiles = paths.map((path) => {
    validatePath(path)
    const bytes = readFileSync(join(source, ...path.split('/')))
    files[path] = new Uint8Array(bytes)
    return { path, size: bytes.byteLength, sha256: createHash('sha256').update(bytes).digest('hex') }
  })
  const { privatePem } = ensureKey()
  const unsigned = { schema: SIGNATURE_SCHEMA, keyId: KEY_ID, algorithm: 'Ed25519', files: signedFiles }
  const signature = sign(null, canonicalPayload(unsigned), createPrivateKey(privatePem)).toString('base64')
  const envelope = { ...unsigned, signature }
  files['signature.json'] = strToU8(JSON.stringify(envelope, null, 2))
  mkdirSync(dirname(output), { recursive: true })
  writeFileSync(output, zipSync(files, { level: 9 }))
  console.log(`Signed ${paths.length} files with ${KEY_ID}: ${output}`)
}

const [command, ...args] = process.argv.slice(2)
if (command === 'init' && args.length === 0) {
  const { publicKey } = ensureKey()
  console.log(`Official skin signing key ready: ${KEY_ID} (${publicKey})`)
} else if (command === 'sign' && args.length === 2) {
  signPackage(args[0], args[1])
} else {
  usage()
}
