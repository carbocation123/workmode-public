import { describe, expect, it } from 'vitest'

import {
  attachPapers,
  buildArchiveFilename,
  createImportedPapers,
  filterPapersByTagIds,
  normalizeSuggestedTag,
  progressPaper,
  resolveArchiveFilenameCollision,
  resolveNoteFilename,
  sectionsWritableByExtractor,
  updateSessionById,
  type TagDefinition,
} from './model'
import { mapBackendPaper } from './literatureApi'

const canonicalTags: TagDefinition[] = [
  {
    id: 'in_situ_characterization',
    name: '原位表征',
    aliases: ['原位测试', 'in-situ', 'operando'],
    category: 'characterization',
    status: 'confirmed',
  },
]

describe('literature frontend model', () => {
  it('maps persistent backend records without inventing extracted facts', () => {
    const paper = mapBackendPaper({
      id: 'paper-1',
      original_filename: 'raw.pdf',
      archive_filename: null,
      archive_location: '文献/未处理',
      title: 'raw',
      authors: '',
      year: null,
      journal: '',
      status: 'pending',
      tags: [],
      focus: '',
      summary: '',
      paper_type: 'unknown',
      metadata_source: 'pending',
      metadata_trust: 'unknown',
      fact_report_path: null,
    })

    expect(paper.filename).toBe('raw.pdf')
    expect(paper.archiveFilename).toBeNull()
    expect(paper.facts).toEqual([])
    expect(paper.factReport).toEqual([])
  })

  it('registers PDFs as pending without pretending that parsing already happened', () => {
    const papers = createImportedPapers(['Wang_2024.pdf', 'notes.txt'])

    expect(papers).toHaveLength(1)
    expect(papers[0]).toMatchObject({ title: 'Wang 2024', status: 'pending', factReport: [] })
  })

  it('progresses through deterministic pipeline states', () => {
    const [paper] = createImportedPapers(['Wang_2024.pdf'])

    expect(progressPaper(paper).status).toBe('parsing')
    expect(progressPaper(progressPaper(paper)).status).toBe('extracting')
    expect(progressPaper(progressPaper(progressPaper(paper))).status).toBe('review')
  })

  it('attaches papers to chat by stable id and does not duplicate them', () => {
    expect(attachPapers(['p-1'], ['p-1', 'p-2'])).toEqual(['p-1', 'p-2'])
  })

  it('reuses canonical tags through aliases and creates provisional tags otherwise', () => {
    expect(normalizeSuggestedTag('Operando', canonicalTags)).toMatchObject({
      id: 'in_situ_characterization',
      status: 'confirmed',
    })
    expect(normalizeSuggestedTag('界面电荷转移', canonicalTags)).toMatchObject({
      name: '界面电荷转移',
      category: 'uncategorized',
      status: 'provisional',
    })
  })

  it('filters papers by every selected canonical tag without enumerating the registry', () => {
    const papers = [
      { id: 'p-1', tagIds: ['epr', 'oxygen_vacancy'] },
      { id: 'p-2', tagIds: ['epr'] },
    ]

    expect(filterPapersByTagIds(papers, ['epr', 'oxygen_vacancy']).map((paper) => paper.id)).toEqual(['p-1'])
    expect(filterPapersByTagIds(papers, [])).toEqual(papers)
  })

  it('builds archive names only from explicit validated metadata', () => {
    expect(buildArchiveFilename('Fierro', 1987, 'JSSC')).toBe('Fierro_1987_JSSC.pdf')
    expect(buildArchiveFilename('Elmutasim', 2024, 'ACSAMI')).toBe('Elmutasim_2024_ACSAMI.pdf')
    expect(buildArchiveFilename('Elmutasim', 2024, 'ACS AMI')).toBeNull()
    expect(buildArchiveFilename('', 2024, 'ACSAMI')).toBeNull()
  })

  it('adds a stable sequence suffix when the standardized archive name already exists', () => {
    expect(resolveArchiveFilenameCollision('Fierro_1987_JSSC.pdf', [])).toBe('Fierro_1987_JSSC.pdf')
    expect(resolveArchiveFilenameCollision('Fierro_1987_JSSC.pdf', ['fierro_1987_jssc.PDF'])).toBe('Fierro_1987_JSSC_2.pdf')
    expect(
      resolveArchiveFilenameCollision('Fierro_1987_JSSC.pdf', [
        'Fierro_1987_JSSC.pdf',
        'Fierro_1987_JSSC_2.pdf',
      ]),
    ).toBe('Fierro_1987_JSSC_3.pdf')
  })

  it('creates safe Markdown note filenames and preserves existing notes', () => {
    expect(resolveNoteFilename('EPR 证据：核查/讨论', [])).toBe('EPR 证据_核查_讨论.md')
    expect(resolveNoteFilename('EPR 证据', ['EPR 证据.md'])).toBe('EPR 证据_2.md')
  })

  it('keeps cross-literature relations outside extractor write scope', () => {
    const sections = [
      { id: 'basic', title: '基本信息', owner: 'extractor' as const, entries: [] },
      { id: 'relations', title: '跨文献关系', owner: 'main_conversation' as const, entries: [] },
    ]

    expect(sectionsWritableByExtractor(sections).map((section) => section.id)).toEqual(['basic'])
  })

  it('updates only the selected conversation session', () => {
    const sessions = [
      { id: 's-1', messages: ['a'], attachedPaperIds: ['p-1'] },
      { id: 's-2', messages: ['b'], attachedPaperIds: [] },
    ]
    const updated = updateSessionById(sessions, 's-2', (session) => ({
      ...session,
      messages: [...session.messages, 'c'],
    }))

    expect(updated[0]).toEqual(sessions[0])
    expect(updated[1].messages).toEqual(['b', 'c'])
  })
})
