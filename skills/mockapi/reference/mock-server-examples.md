# Mock Server Examples

These examples show the preferred Clear-style feature shape. Adapt names and
generated imports to the target contract.

Generated `src/generated/mock-admin/state/**` files are admin infrastructure. Do
not edit them by hand; use generated contract exports or feature-local aliases
in feature modules when behavior needs named domain record types.

Keep `src/lib` for product-agnostic infrastructure helpers such as clone,
errors, IDs, request context, soft delete, and sorting. Put product/domain
helpers under the owning feature.

Example feature-local alias:

```ts
import type { MockState } from '../../generated/mock-admin/contract/index.ts'

type WorkspaceRecord = MockState['workspaces'][number]
```

## Repository Method Vocabulary

Use this vocabulary unless the product behavior clearly needs a more specific
name:

- Collection reads: `all`, `visible`, `find`, `require`.
- Collection mutations: `create`, `update`, `markDeleted`, `restore`, `remove`.
- Selectors: `listBy<Relation>`, `<thing>Ids`, `<thing>Segments`.
- Singleton slices: `get`, `set`, `update`, `reset`.
- Nested singleton collections: `requireItem`, `addItem`, `removeItem`, `empty`.
- Domain mutations: `touch`, `set<Field>`, `append<Field>`,
  `complete<Field>`.

Avoid exposing generic `byId`, `setAll`, `setItems`, or `replaceAll` as
service-facing repository APIs. Lookup by id is expected, but prefer `find(id)`
for optional reads and `require(id)` for not-found validation. Whole-slice
replacement is allowed when it is the actual domain operation, but expose it
through a named repository method such as `resetToDefaults`, `syncFromSnapshot`,
`replaceImportedItems`, `reorder`, or `empty`, and keep the raw `setSlice` / array replacement
inside the repository.

## Composition Root

Create dependencies once in `src/dependencies.ts`: state store first, then
repositories, derived resolvers, and services. `src/controllers.ts` creates the
store, calls `newMockApiDependencies(stateStore)`, and aggregates operation
controllers.

```ts
const workspacesRepository = new WorkspaceRepository(stateStore)
const foldersRepository = new FolderRepository(stateStore)
const decksRepository = new DeckRepository(stateStore)
const trashRepository = new TrashRepository(stateStore)

const locationPathResolver = new LocationPathResolver(
  decksRepository,
  foldersRepository,
  workspacesRepository,
)

const folderService = new FolderService(
  foldersRepository,
  locationPathResolver,
  stateStore,
  workspacesRepository,
  trashRepository,
)

const deps: MockApiDependencies = {
  folderService,
  stateStore,
}
```

Do not instantiate feature repositories inside operation controllers or inside
service methods.

## Feature Repository

Repositories own collection access and mutation for their feature slices. A
service should call named methods such as `create`, `update`, `markDeleted`,
`restore`, `remove`, and feature selectors; do not make the service read an
entire array, modify it, and write it back.

```ts
import { notFound } from '../../generated/product-api/mock-runtime.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'
import type { MockStateStore } from '../../lib/stateStore.ts'
import { sortByPreference, type SortPreference } from '../../lib/sort.ts'
import { visible } from '../../lib/softDelete.ts'

type FolderRecord = MockState['folders'][number]

export class FolderRepository {
  constructor(private readonly stateStore: MockStateStore) {}

  all() {
    return this.stateStore.findEntities('folders')
  }

  visible() {
    return visible(this.all())
  }

  find(folderId: string) {
    return this.stateStore.findEntity('folders', folderId)
  }

  require(folderId: string, options: { includeDeleted?: boolean } = {}) {
    const candidates = options.includeDeleted ? this.all() : this.visible()
    const folder = candidates.find((candidate) => candidate.id === folderId)

    if (!folder) {
      throw notFound('folder', folderId)
    }

    return folder
  }

  async create(folder: FolderRecord) {
    return this.stateStore.createEntity('folders', folder, { prepend: true })
  }

  async update(folderId: string, updater: (folder: FolderRecord) => FolderRecord) {
    return (
      await this.stateStore.updateEntity('folders', folderId, updater)
    ) ?? this.require(folderId, { includeDeleted: true })
  }

  async markDeleted(folderId: string, deletedAt: string) {
    return this.update(folderId, (folder) => ({ ...folder, deletedAt }))
  }

  async restore(folderId: string) {
    return this.update(folderId, (folder) => {
      const { deletedAt: _deletedAt, ...restored } = folder
      return restored
    })
  }

  async remove(folderId: string) {
    return this.stateStore.deleteEntity('folders', folderId)
  }

  listByParent(workspaceId: string, parentId: string, sort?: SortPreference) {
    const folders = this.visible().filter(
      (folder) => folder.workspaceId === workspaceId && folder.parentId === parentId,
    )

    return sort ? sortByPreference(folders, sort) : folders
  }

  descendantIds(folderId: string): string[] {
    const children = this.visible().filter((folder) => folder.parentId === folderId)
    return children.flatMap((folder) => [folder.id, ...this.descendantIds(folder.id)])
  }
}
```

Singleton-style repositories should still expose named mutations instead of a
raw `setItems` API:

```ts
import { notFound } from '../../generated/product-api/mock-runtime.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'
import type { MockStateStore } from '../../lib/stateStore.ts'

type TrashState = MockState['trash']

export class TrashRepository {
  constructor(private readonly stateStore: MockStateStore) {}

  get() {
    return this.stateStore.getSlice('trash')
  }

  requireItem(itemId: string) {
    const item = this.get().items.find((candidate) => candidate.id === itemId)

    if (!item) {
      throw notFound('trash item', itemId)
    }

    return item
  }

  async addItem(item: TrashState['items'][number]) {
    const trash = this.get()

    await this.stateStore.setSlice('trash', {
      ...trash,
      items: [item, ...trash.items.filter((candidate) => candidate.id !== item.id)],
    })

    return this.get()
  }

  async removeItem(itemId: string) {
    const trash = this.get()

    await this.stateStore.setSlice('trash', {
      ...trash,
      items: trash.items.filter((item) => item.id !== itemId),
    })

    return this.get()
  }

  async empty(lastEmptiedAt: string) {
    await this.stateStore.setSlice('trash', {
      items: [],
      lastEmptiedAt,
    })

    return this.get()
  }
}
```

## Feature Service

Allocate IDs once per transaction and pass the allocator into helper methods
that need additional IDs. Services orchestrate transactions, validation, and
cross-feature calls; repositories perform the collection mutation.

```ts
import type {
  Folder,
  FolderDraft,
} from '../../generated/product-api/contract/index.ts'
import { clone } from '../../lib/clone.ts'
import { newIdAllocator } from '../../lib/ids.ts'
import type { MockStateStore } from '../../lib/stateStore.ts'
import type { LocationPathResolver } from '../location-path/resolver.ts'
import type { TrashRepository } from '../trash/repository.ts'
import type { WorkspaceRepository } from '../workspaces/repository.ts'
import type { FolderRepository } from './repository.ts'

export class FolderService {
  constructor(
    private readonly folders: FolderRepository,
    private readonly paths: LocationPathResolver,
    private readonly stateStore: MockStateStore,
    private readonly workspaces: WorkspaceRepository,
    private readonly trash: TrashRepository,
  ) {}

  async create(draft: FolderDraft): Promise<Folder> {
    const workspaceId = this.workspaceIdForParent(draft.parentId)

    return this.stateStore.transaction(async () => {
      const ids = newIdAllocator(this.stateStore.getSlice('idCounters'))
      const folder: Folder = {
        ...draft,
        id: ids.next('folder'),
        updatedAt: this.stateStore.now(),
        workspaceId,
      }

      await this.folders.create(folder)
      await this.workspaces.touch(workspaceId, this.stateStore.now())

      return clone(folder)
    })
  }

  async update(folderId: string, draft: FolderDraft): Promise<Folder> {
    const current = this.folders.require(folderId)
    const workspaceId = this.workspaceIdForParent(draft.parentId)

    return this.stateStore.transaction(async () => {
      const folder = await this.folders.update(folderId, (existing) => ({
        ...existing,
        ...draft,
        updatedAt: this.stateStore.now(),
        workspaceId,
      }))

      await this.workspaces.touch(workspaceId, this.stateStore.now())
      if (current.workspaceId !== workspaceId) {
        await this.workspaces.touch(current.workspaceId, this.stateStore.now())
      }

      return clone(folder)
    })
  }

  async delete(folderId: string) {
    const folder = this.folders.require(folderId)

    await this.stateStore.transaction(async () => {
      const deletedAt = this.stateStore.now()

      await this.folders.markDeleted(folderId, deletedAt)
      await this.trash.addItem({
        deletedAt,
        id: folder.id,
        kind: 'folder',
        locationPath: this.paths.folderContainerPathSegments(folder),
        title: folder.name,
      })
      await this.workspaces.touch(folder.workspaceId, deletedAt)
    })
  }

  private workspaceIdForParent(parentId: string) {
    const workspace = this.workspaces.find(parentId)
    if (workspace) {
      return this.workspaces.require(parentId).id
    }

    const parent = this.folders.require(parentId)
    this.workspaces.require(parent.workspaceId)

    return parent.workspaceId
  }
}
```

Avoid this service-level read-copy-write shape:

```ts
const folders = this.folders.all()
this.folders.setAll([...folders, folder])
```

Prefer a named repository mutation:

```ts
await this.folders.create(folder)
```

## Soft Delete and Trash Flow

Delete operations should usually mark the resource deleted and add a trash item;
restore operations should go through the trash feature and call feature
repository `restore` methods.

```ts
async delete(folderId: string) {
  const folder = this.folders.require(folderId)

  await this.stateStore.transaction(async () => {
    const deletedAt = this.stateStore.now()

    await this.folders.markDeleted(folderId, deletedAt)
    await this.trash.addItem({
      deletedAt,
      id: folder.id,
      kind: 'folder',
      locationPath: this.paths.folderContainerPathSegments(folder),
      title: folder.name,
    })
    await this.workspaces.touch(folder.workspaceId, deletedAt)
  })
}

async restore(itemId: string) {
  const item = this.trash.requireItem(itemId)

  await this.stateStore.transaction(async () => {
    if (item.kind === 'folder') {
      await this.folders.restore(itemId)
    }

    await this.trash.removeItem(itemId)
  })
}
```

## Denormalized Counters

Keep derived counters and timestamp updates behind named repository methods.
For example, when notes are created or deleted, update the owning deck through
`bumpTotalNotes` instead of rebuilding deck arrays in the note service.

```ts
export class WorkspaceRepository {
  async touch(workspaceId: string, updatedAt: string) {
    return this.update(workspaceId, (workspace) => ({
      ...workspace,
      updatedAt,
    }))
  }
}

export class DeckRepository {
  async bumpTotalNotes(deckId: string, amount: number, updatedAt: string) {
    return this.update(deckId, (deck) => ({
      ...deck,
      totalNotes: Math.max(0, deck.totalNotes + amount),
      updatedAt,
    }))
  }
}

export class NoteService {
  async create(draft: NoteDraft) {
    const deck = this.decks.require(draft.deckId)

    return this.stateStore.transaction(async () => {
      const note = this.buildNote(draft)

      await this.notes.create(note)
      await this.decks.bumpTotalNotes(draft.deckId, 1, this.stateStore.now())
      await this.workspaces.touch(deck.workspaceId, this.stateStore.now())

      return clone({ id: note.id, deckId: note.deckId })
    })
  }
}
```

## Feature-Local Domain Helper

Put product helpers beside the feature that owns the rule. For example, note
card parsing and note search text belong in `src/features/notes/noteDetails.ts`,
not `src/lib/notes.ts`.

```ts
import type { ClozeNoteCard, NoteDetail } from '../../generated/product-api/contract/index.ts'
import { newIdAllocator } from '../../lib/ids.ts'

export const noteSearchText = (note: NoteDetail) =>
  [
    note.title,
    note.kind === 'basic' ? note.editor.front : note.editor.body,
    note.kind === 'basic' ? note.editor.back : '',
  ]
    .join(' ')
    .toLowerCase()

export const clozeCardsFromBody = ({
  body,
  existingCards = [],
  ids,
  now,
}: {
  body: string
  existingCards?: ClozeNoteCard[]
  ids: ReturnType<typeof newIdAllocator>
  now: string
}) => {
  const existingByClozeId = new Map(existingCards.map((card) => [card.clozeId, card]))
  const markers = [...body.matchAll(/\{\{(c\d+)::(.*?)\}\}/g)]

  return markers.map((marker): ClozeNoteCard => {
    const existing = existingByClozeId.get(marker[1])
    return existing
      ? { ...existing, title: marker[2] }
      : {
          clozeId: marker[1],
          dueAt: now,
          id: ids.next('card'),
          progress: 0,
          reviewedAt: now,
          status: 'in-progress',
          title: marker[2],
        }
  })
}
```

## Read-Only Composite Service

Composite features such as search may read named selectors from several
repositories. They should not write product slices or perform repository
collection replacement.

```ts
export class ContentSearchService {
  constructor(
    private readonly decks: DeckRepository,
    private readonly folders: FolderRepository,
    private readonly notes: NoteRepository,
    private readonly paths: LocationPathResolver,
    private readonly workspaces: WorkspaceRepository,
  ) {}

  search(query: string, workspaceId: string) {
    const normalized = query.trim().toLowerCase()
    const workspace = this.workspaces.require(workspaceId)

    if (!normalized) {
      return []
    }

    const notes = this.notes
      .visible()
      .filter((note) => noteSearchText(note).includes(normalized))

    return clone(
      notes.map((note) => ({
        id: note.id,
        kind: 'note',
        locationPath: this.paths.noteContainerPathSegments(note),
        title: note.title,
        workspaceId: workspace.id,
      })),
    )
  }
}
```

## Cross-Feature Resolver

When derived behavior spans several features, create a small named feature
service or resolver instead of a broad `src/lib/tree.ts` or `src/lib/domain.ts`.

```ts
import type { Deck, Folder, NoteDetail } from '../../generated/product-api/contract/index.ts'
import type { DeckRepository } from '../decks/repository.ts'
import type { FolderRepository } from '../folders/repository.ts'
import type { WorkspaceRepository } from '../workspaces/repository.ts'

export class LocationPathResolver {
  constructor(
    private readonly decks: DeckRepository,
    private readonly folders: FolderRepository,
    private readonly workspaces: WorkspaceRepository,
  ) {}

  folderContainerPathSegments(folder: Folder) {
    return [
      this.workspaces.title(folder.workspaceId),
      ...(folder.parentId === folder.workspaceId ? [] : this.folders.pathSegments(folder.parentId)),
    ]
  }

  deckContainerPathSegments(deck: Deck) {
    return [
      this.workspaces.title(deck.workspaceId),
      ...(deck.parentId === deck.workspaceId ? [] : this.folders.pathSegments(deck.parentId)),
    ]
  }

  noteContainerPathSegments(note: NoteDetail) {
    const deck = this.decks.find(note.deckId)
    return deck ? [...this.deckContainerPathSegments(deck), deck.title] : [note.deckId]
  }
}
```

## Operation Controller Adapter

Generated operation controllers start as TODO adapters. Replace the TODO with a
thin service call:

```ts
import type { MockApiDependencies, ProductMockControllers } from '../../../controllers.ts'

export const newCreateWorkspaceController = (
  deps: MockApiDependencies,
): Pick<ProductMockControllers, 'createWorkspace'> => ({
  createWorkspace: async ({ body }) => deps.workspaceService.create(body),
})
```

For OpenAPI path parameters, use `input.path` from the generated `openapi-ts`
operation data. Do not use `input.params`.

```ts
export const newListWorkspaceDecksController = (
  deps: MockApiDependencies,
): Pick<ProductMockControllers, 'listWorkspaceDecks'> => ({
  listWorkspaceDecks: async ({ path, query }) =>
    deps.decksService.listWorkspaceDecks(path.workspaceId, query),
})
```

## Feature Seed

```ts
import type { SeedContext } from '../../generated/mock-admin/state/seed.ts'
import type { MockState } from '../../generated/mock-admin/contract/index.ts'

type WorkspaceRecord = MockState['workspaces'][number]

export const seedWorkspaces = ({ fromSeedNow }: SeedContext): Pick<MockState, 'workspaces'> => ({
  workspaces: [
    {
      id: 'default-workspace',
      title: 'Default Workspace',
      updatedAt: fromSeedNow(-1),
    } satisfies WorkspaceRecord,
  ],
})
```

## Admin Seed Aggregator

Keep seed records in feature-local seed files. Generated
`src/generated/mock-admin/state/seed.ts` creates the shared seed context,
initializes global mock state, and spreads feature seeds:

```ts
import { seedWorkspaces } from '../../features/workspaces/seed.ts'
import type { MockState } from '../contract/index.ts'

export type SeedContext = {
  fromSeedNow: (days: number) => string
  seedNow: string
}

const seedNow = '2026-05-16T12:00:00.000Z'
const dayMs = 24 * 60 * 60 * 1000

const newSeedContext = (): SeedContext => ({
  fromSeedNow: (days) => new Date(Date.parse(seedNow) + days * dayMs).toISOString(),
  seedNow,
})

export const seedState = (): MockState => {
  const context = newSeedContext()

  return {
    schemaVersion: 1,
    clock: {
      now: context.seedNow,
    },
    idCounters: {
      workspace: 1,
    },
    ...seedWorkspaces(context),
  }
}
```
