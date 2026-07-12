const DB_NAME = 'workmode-public-official-skins-v1'
const DB_VERSION = 1
const STORE_NAME = 'assets'
export const SKIN_LAYOUT_ASSET_ID = '__official_layout_css__'
export const SKIN_VISUAL_ASSET_ID = '__official_visual_css__'
export const LEGACY_SKIN_DATABASE_NAME = 'workmode-public-skins-v3'

interface StoredSkinAsset {
  key: string
  skinId: string
  assetId: string
  blob: Blob
}

function openDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('当前环境不支持皮肤资源仓库'))
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'key' })
        store.createIndex('skinId', 'skinId', { unique: false })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('无法打开皮肤资源仓库'))
  })
}

function transactionDone(transaction: IDBTransaction) {
  return new Promise<void>((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error || new Error('皮肤资源事务失败'))
    transaction.onabort = () => reject(transaction.error || new Error('皮肤资源事务已中止'))
  })
}

function requestResult<T>(request: IDBRequest<T>) {
  return new Promise<T>((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('皮肤资源读取失败'))
  })
}

export async function replaceSkinAssets(skinId: string, assets: Map<string, Blob>) {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    const done = transactionDone(transaction)
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('skinId')
    const cursorRequest = index.openKeyCursor(IDBKeyRange.only(skinId))
    cursorRequest.onsuccess = () => {
      const cursor = cursorRequest.result
      if (cursor) {
        store.delete(cursor.primaryKey)
        cursor.continue()
        return
      }
      assets.forEach((blob, assetId) => {
        const record: StoredSkinAsset = { key: `${skinId}:${assetId}`, skinId, assetId, blob }
        store.put(record)
      })
    }
    cursorRequest.onerror = () => transaction.abort()
    await done
  } finally {
    database.close()
  }
}

export async function replaceOfficialSkinAssets(
  skinId: string,
  assets: Map<string, Blob>,
  styles: { layout: Blob; visual: Blob }
) {
  const complete = new Map(assets)
  complete.set(SKIN_LAYOUT_ASSET_ID, styles.layout)
  complete.set(SKIN_VISUAL_ASSET_ID, styles.visual)
  await replaceSkinAssets(skinId, complete)
}

export async function loadSkinAssets(skinId: string) {
  const database = await openDatabase()
  try {
    const transaction = database.transaction(STORE_NAME, 'readonly')
    const done = transactionDone(transaction)
    const recordsRequest = requestResult(transaction.objectStore(STORE_NAME).index('skinId').getAll(IDBKeyRange.only(skinId))) as Promise<StoredSkinAsset[]>
    const [records] = await Promise.all([recordsRequest, done])
    return new Map(records.map((record) => [record.assetId, record.blob]))
  } finally {
    database.close()
  }
}

export async function removeSkinAssets(skinId: string) {
  await replaceSkinAssets(skinId, new Map())
}

export function removeLegacySkinAssetDatabase() {
  if (typeof indexedDB === 'undefined') return
  indexedDB.deleteDatabase(LEGACY_SKIN_DATABASE_NAME)
}
