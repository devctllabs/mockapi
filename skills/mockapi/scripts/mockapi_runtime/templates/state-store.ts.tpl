{{STARTER_HEADER}}import { Collection } from '@msw/data'

import { clone } from './clone.ts'
import type {
  MockClock,
  MockState,
} from '../generated/mock-admin/contract/index.ts'
{{ZOD_IMPORT}}import { seedState } from '../generated/mock-admin/state/seed.ts'

export type EntitySliceKey = {{ENTITY_UNION}}

type EntityRecord<TKey extends EntitySliceKey> =
  EntityRecordMap[TKey]

type EntityRecordMap = {
{{ENTITY_RECORD_MAP}}
}

type EntityCollection<TRecord extends object> = {
  all: () => TRecord[]
  clear: () => void
  create: (record: TRecord) => Promise<TRecord>
  delete: (record: TRecord) => TRecord | undefined
  findFirst: (
    predicate?: (query: { where: (predicate: unknown) => unknown }) => unknown,
  ) => TRecord | undefined
  update: (
    record: TRecord,
    options: { data: (draft: TRecord) => void },
  ) => Promise<TRecord | undefined>
}

type EntityCollections = ReturnType<typeof newEntityCollections>
type MetaState = Omit<MockState, EntitySliceKey>

export type MockStatePersist = (state: MockState) => Promise<void> | void

export type MswDataStateStoreOptions = {
  initialState?: MockState
  persist?: MockStatePersist
}

export interface MockStateStore {
  createEntity<TKey extends EntitySliceKey>(
    key: TKey,
    record: EntityRecord<TKey>,
    options?: { prepend?: boolean },
  ): Promise<EntityRecord<TKey>>
  deleteEntity<TKey extends EntitySliceKey>(
    key: TKey,
    id: string,
  ): Promise<EntityRecord<TKey> | undefined>
  daysFromNow(days: number): string
  findEntity<TKey extends EntitySliceKey>(
    key: TKey,
    id: string,
  ): EntityRecord<TKey> | undefined
  findEntities<TKey extends EntitySliceKey>(
    key: TKey,
    predicate?: (record: EntityRecord<TKey>) => boolean,
  ): Array<EntityRecord<TKey>>
  getSlice<TKey extends keyof MockState>(key: TKey): MockState[TKey]
  now(): string
  replace(state: MockState): Promise<MockState>
  reset(): Promise<MockState>
  setClock(now: string): Promise<MockClock>
  setSlice<TKey extends keyof MockState>(key: TKey, value: MockState[TKey]): Promise<void>
  snapshot(): MockState
  transaction<T>(callback: () => Promise<T> | T): Promise<T>
  updateEntity<TKey extends EntitySliceKey>(
    key: TKey,
    id: string,
    updater: (record: EntityRecord<TKey>) => EntityRecord<TKey>,
  ): Promise<EntityRecord<TKey> | undefined>
}

const dayMs = 24 * 60 * 60 * 1000

const entitySliceKeys = [
{{ENTITY_KEYS}}
] as const satisfies readonly EntitySliceKey[]

const entityIdFields = {
{{ENTITY_ID_FIELDS}}
} as const satisfies Record<EntitySliceKey, string>

const newEntityCollections = () => ({
{{ENTITY_COLLECTIONS}}
})

const isEntitySliceKey = (key: keyof MockState): key is EntitySliceKey =>
  entitySliceKeys.includes(key as EntitySliceKey)

const metaFromState = (state: MockState): MetaState => ({
{{META_PROPERTIES}}
})

const replaceDraft = <TRecord extends object>(draft: TRecord, next: TRecord) => {
  const draftRecord = draft as Record<string, unknown>
  const nextRecord = next as Record<string, unknown>

  for (const key of Object.keys(draftRecord)) {
    if (!(key in nextRecord)) {
      delete draftRecord[key]
    }
  }

  Object.assign(draftRecord, nextRecord)
}

export class MswDataStateStore implements MockStateStore {
  private readonly collections: EntityCollections = newEntityCollections()
  private readonly persistState: MockStatePersist | undefined
  private meta: MetaState = metaFromState(seedState())

  constructor(options: Pick<MswDataStateStoreOptions, 'persist'> = {}) {
    this.persistState = options.persist
  }

  async reset() {
    return this.replace(seedState())
  }

  async replace(state: MockState) {
    await this.replaceState(state)
    await this.persist()

    return this.snapshot()
  }

  async setClock(now: string) {
    this.meta.clock = { now }
    await this.persist()

    return clone(this.meta.clock)
  }

  getSlice<TKey extends keyof MockState>(key: TKey): MockState[TKey] {
    if (isEntitySliceKey(key)) {
      return this.entitySnapshot(key) as MockState[TKey]
    }

    return this.meta[key as keyof MetaState] as MockState[TKey]
  }

  async setSlice<TKey extends keyof MockState>(key: TKey, value: MockState[TKey]) {
    if (isEntitySliceKey(key)) {
      await this.replaceEntitySlice(key, value as unknown as Array<EntityRecord<typeof key>>)
      return
    }

    this.meta = {
      ...this.meta,
      [key]: clone(value),
    }
  }

  findEntities<TKey extends EntitySliceKey>(
    key: TKey,
    predicate: (record: EntityRecord<TKey>) => boolean = () => true,
  ): Array<EntityRecord<TKey>> {
    return this.collection(key)
      .all()
      .filter((record) => predicate(this.toPlainRecord(record)))
      .map((record) => this.toPlainRecord(record))
  }

  findEntity<TKey extends EntitySliceKey>(key: TKey, id: string) {
    const record = this.findInternalEntity(key, id)

    return record ? this.toPlainRecord(record) : undefined
  }

  async createEntity<TKey extends EntitySliceKey>(
    key: TKey,
    record: EntityRecord<TKey>,
    options: { prepend?: boolean } = {},
  ): Promise<EntityRecord<TKey>> {
    const collection = this.collection(key)
    const created = await collection.create(clone(record))

    if (options.prepend) {
      const records = collection.all()
      const appended = records.pop()

      if (appended) {
        records.unshift(appended)
      }
    }

    return this.toPlainRecord(created)
  }

  async updateEntity<TKey extends EntitySliceKey>(
    key: TKey,
    id: string,
    updater: (record: EntityRecord<TKey>) => EntityRecord<TKey>,
  ) {
    const collection = this.collection(key)
    const current = this.findInternalEntity(key, id)

    if (!current) {
      return undefined
    }

    const next = updater(this.toPlainRecord(current))
    const updated = await collection.update(current, {
      data: (draft) => replaceDraft(draft, next),
    })

    return updated ? this.toPlainRecord(updated) : undefined
  }

  async deleteEntity<TKey extends EntitySliceKey>(key: TKey, id: string) {
    const current = this.findInternalEntity(key, id)

    if (!current) {
      return undefined
    }

    return this.toPlainRecord(this.collection(key).delete(current) ?? current)
  }

  snapshot(): MockState {
    return {
{{SNAPSHOT_PROPERTIES}}
    }
  }

  now() {
    return this.meta.clock.now
  }

  daysFromNow(days: number) {
    return new Date(Date.parse(this.now()) + days * dayMs).toISOString()
  }

  async transaction<T>(callback: () => Promise<T> | T): Promise<T> {
    const result = await callback()
    await this.persist()

    return result
  }

  private collection<TKey extends EntitySliceKey>(key: TKey) {
    return this.collections[key] as unknown as EntityCollection<EntityRecord<TKey>>
  }

  private findInternalEntity<TKey extends EntitySliceKey>(key: TKey, id: string) {
    const idField = entityIdFields[key] as keyof EntityRecord<TKey>

    return this.collection(key).findFirst((query) =>
      query.where((record: EntityRecord<TKey>) => String(record[idField]) === id),
    )
  }

  private entitySnapshot<TKey extends EntitySliceKey>(key: TKey): MockState[TKey] {
    return this.collection(key)
      .all()
      .map((record) => this.toPlainRecord(record)) as MockState[TKey]
  }

  private async replaceState(state: MockState) {
    this.meta = metaFromState(state)

    for (const key of entitySliceKeys) {
      await this.replaceEntitySlice(key, state[key] as unknown as Array<EntityRecord<typeof key>>)
    }
  }

  private async replaceEntitySlice<TKey extends EntitySliceKey>(
    key: TKey,
    records: Array<EntityRecord<TKey>>,
  ) {
    const collection = this.collection(key)

    collection.clear()
    for (const record of records) {
      await collection.create(clone(record) as EntityRecord<TKey>)
    }
  }

  private toPlainRecord<TRecord extends object>(record: TRecord): TRecord {
    return clone({ ...record }) as TRecord
  }

  private async persist() {
    await this.persistState?.(this.snapshot())
  }
}

export const newMswDataStateStore = async (
  options: MswDataStateStoreOptions = {},
): Promise<MswDataStateStore> => {
  const store = new MswDataStateStore({ persist: options.persist })

  await store.replace(options.initialState ?? seedState())

  return store
}

export const newMemoryMockStateStore = (initialState: MockState = seedState()) =>
  newMswDataStateStore({ initialState })
