import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Brain,
  Hash,
  Tags,
  Layers,
  BarChart2,
  Key,
  Info,
  Search,
  CheckCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { documentsApi } from '../api/documents';
import { nlpApi } from '../api/nlp';
import { Badge } from '../components/common/Badge';

export const NLPAnalysis = () => {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get('documentId') || '';

  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(initialDocId);
  const [activeTab, setActiveTab] = useState('preprocessing'); // preprocessing, pos, ner, ngrams, frequency, topics
  const [sampleSize, setSampleSize] = useState(300);

  const [loading, setLoading] = useState(false);
  const [preprocData, setPreprocData] = useState(null);
  const [posData, setPosData] = useState(null);
  const [nerData, setNerData] = useState(null);
  const [ngramsData, setNgramsData] = useState(null);
  const [freqData, setFreqData] = useState(null);
  const [keywordsData, setKeywordsData] = useState(null);
  const [topicsData, setTopicsData] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [selectedTerm, setSelectedTerm] = useState('');

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await documentsApi.list();
        const items = res.items || [];
        setDocuments(items);
        if (!selectedDocId && items.length > 0) {
          setSelectedDocId(items[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchDocs();
  }, []);

  const loadTabData = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      if (activeTab === 'preprocessing') {
        const data = await nlpApi.getDocumentPreprocessing(selectedDocId, sampleSize);
        setPreprocData(data);
      } else if (activeTab === 'pos') {
        const data = await nlpApi.getPOS(selectedDocId, sampleSize);
        setPosData(data);
      } else if (activeTab === 'ner') {
        const data = await nlpApi.getEntities(selectedDocId);
        setNerData(data);
      } else if (activeTab === 'ngrams') {
        const data = await nlpApi.getNgrams(selectedDocId, 2);
        setNgramsData(data);
      } else if (activeTab === 'frequency') {
        const data = await nlpApi.getWordFrequency(selectedDocId, 20);
        setFreqData(data);
      } else if (activeTab === 'topics') {
        const [kw, tp] = await Promise.all([
          nlpApi.getKeywords(selectedDocId),
          nlpApi.getTopics(selectedDocId),
        ]);
        setKeywordsData(kw);
        setTopicsData(tp);
      }
    } catch (err) {
      console.error('Failed to load NLP data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTabData();
  }, [selectedDocId, activeTab, sampleSize]);

  const handleTermClick = async (term) => {
    setSelectedTerm(term);
    try {
      const res = await nlpApi.searchTerm(selectedDocId, term);
      setSearchResults(res);
    } catch (e) {
      console.error('Term search failed:', e);
    }
  };

  const EXPLANATIONS = {
    preprocessing:
      'Text cleaning normalizes whitespace, removes bullet markers, handles hyphenation at line breaks, eliminates punctuation and English stopwords, and computes Porter & Snowball stems alongside spaCy lemmatization.',
    pos: 'Part-of-Speech (POS) tagging uses statistical linguistic models (spaCy) to assign syntactic categories (Noun, Verb, Adjective, Adverb) to every token.',
    ner: 'Named Entity Recognition (NER) detects and categorizes real-world proper names and technical entities (Organizations, People, Geopolitical Entities, Dates, Numbers).',
    ngrams:
      'N-grams are contiguous sequences of N items from a given text. Useful for identifying multi-word domain terminology and collocations.',
    frequency:
      'Word frequency distributions count raw and normalized occurrences of lexical terms across the document, highlighting key technical vocabulary.',
    topics:
      'Combines Latent Dirichlet Allocation (LDA) unsupervised topic modeling with RAKE, TF-IDF keywords, and KMeans clustering of sentence embeddings.',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Interactive NLP Analysis
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Explore authentic linguistic transformations, syntactic tagging, named entities, and topic modeling computed locally.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            className="rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-xs font-semibold text-slate-800 dark:text-white focus:outline-none"
          >
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.original_filename}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-surface-darkBorder space-x-4 overflow-x-auto text-xs font-semibold">
        {[
          { key: 'preprocessing', label: 'Preprocessing' },
          { key: 'pos', label: 'POS Tagging' },
          { key: 'ner', label: 'Named Entities (NER)' },
          { key: 'ngrams', label: 'N-grams' },
          { key: 'frequency', label: 'Word Frequency' },
          { key: 'topics', label: 'Keywords & Topics' },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => {
              setActiveTab(t.key);
              setSearchResults(null);
            }}
            className={`pb-3 whitespace-nowrap transition-colors ${
              activeTab === t.key
                ? 'border-b-2 border-primary-600 text-primary-600 dark:text-primary-400'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Educational Explanation Banner */}
      <div className="flex items-start gap-3 rounded-xl bg-primary-50/60 dark:bg-primary-950/30 border border-primary-200/60 dark:border-primary-900/40 p-4 text-xs text-primary-900 dark:text-primary-200">
        <Info className="h-4 w-4 shrink-0 mt-0.5 text-primary-600 dark:text-primary-400" />
        <div>
          <span className="font-bold">Educational Insight: </span>
          <span>{EXPLANATIONS[activeTab]}</span>
        </div>
      </div>

      {/* TAB 1: PREPROCESSING */}
      {activeTab === 'preprocessing' && preprocData && (
        <div className="space-y-6">
          {/* Stat Cards Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
              <p className="text-xs text-slate-400 font-semibold uppercase">Total Tokens</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {preprocData.stats?.total_tokens ?? 0}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
              <p className="text-xs text-slate-400 font-semibold uppercase">Unique Tokens (Vocabulary)</p>
              <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {preprocData.stats?.unique_tokens ?? 0}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4">
              <p className="text-xs text-slate-400 font-semibold uppercase">After Stopwords Removed</p>
              <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                {preprocData.stats?.tokens_after_stopwords ?? 0}
              </p>
            </div>
          </div>

          {/* Side-by-side Original vs Cleaned Text */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-2">Original Text Sample</h3>
              <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-3.5 font-mono text-xs text-slate-700 dark:text-slate-300 max-h-64 overflow-y-auto whitespace-pre-wrap">
                {preprocData.sample_original || 'No text sample'}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-2">Normalized & Cleaned Text</h3>
              <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-3.5 font-mono text-xs text-slate-700 dark:text-slate-300 max-h-64 overflow-y-auto whitespace-pre-wrap">
                {preprocData.sample_cleaned || 'No text sample'}
              </div>
            </div>
          </div>

          {/* Lemmatized Token Chips */}
          <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">
              Lemmatized Tokens (spaCy)
            </h3>
            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
              {(preprocData.lemmatized_sample || []).map((token, i) => (
                <span
                  key={i}
                  className="rounded-lg bg-slate-100 dark:bg-slate-800 px-2.5 py-1 font-mono text-xs text-slate-800 dark:text-slate-200"
                >
                  {token}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: POS TAGGING */}
      {activeTab === 'pos' && posData && (
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-4">
          <h3 className="font-bold text-sm text-slate-900 dark:text-white">
            Tagged Token Stream (Universal POS)
          </h3>
          <div className="flex flex-wrap gap-2 leading-relaxed">
            {(posData.tokens || []).map((t, i) => {
              const isNoun = t.pos === 'NOUN' || t.pos === 'PROPN';
              const isVerb = t.pos === 'VERB';
              const isAdj = t.pos === 'ADJ';
              return (
                <span
                  key={i}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-mono ${
                    isNoun
                      ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 border border-blue-200 dark:border-blue-900'
                      : isVerb
                      ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-900'
                      : isAdj
                      ? 'bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-200 dark:border-purple-900'
                      : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400'
                  }`}
                >
                  <span className="font-semibold">{t.text}</span>
                  <span className="text-[10px] opacity-70">[{t.pos}]</span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: NER */}
      {activeTab === 'ner' && nerData && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(nerData.entity_counts || {}).map(([label, count]) => (
              <div key={label} className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-3">
                <p className="text-[11px] font-semibold text-slate-400 uppercase">{label}</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">{count}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">Extracted Entities</h3>
            <div className="divide-y divide-slate-100 dark:divide-surface-darkBorder">
              {(nerData.entities || []).map((ent, i) => (
                <div key={i} className="py-2.5 flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-900 dark:text-white">{ent.text}</span>
                  <Badge variant="primary">{ent.label}</Badge>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: N-GRAMS */}
      {activeTab === 'ngrams' && ngramsData && (
        <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
          <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">Top Bigrams (Collocations)</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {(ngramsData.ngrams || []).map((ng, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 text-xs">
                <span className="font-mono text-slate-800 dark:text-slate-200">{ng.phrase}</span>
                <span className="rounded-full bg-primary-100 text-primary-700 dark:bg-primary-950 dark:text-primary-300 px-2 py-0.5 text-[10px] font-bold">
                  {ng.count}x
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 5: WORD FREQUENCY */}
      {activeTab === 'frequency' && freqData && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-4">
              Top 20 Technical Term Frequencies
            </h3>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={freqData.frequencies || []}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="word" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#5B3FD0" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* TAB 6: KEYWORDS & TOPICS */}
      {activeTab === 'topics' && (
        <div className="space-y-6">
          {/* Clickable Keywords */}
          <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-2">
              Extracted Keywords (Click to jump to document passages)
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Ranked with RAKE, TF-IDF, and TextRank co-occurrence scoring.
            </p>
            <div className="flex flex-wrap gap-2">
              {(keywordsData?.keywords || []).map((kw, i) => (
                <button
                  key={i}
                  onClick={() => handleTermClick(kw.term)}
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold transition-all ${
                    selectedTerm === kw.term
                      ? 'bg-primary-600 text-white shadow-sm'
                      : 'bg-primary-50 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300 hover:bg-primary-100'
                  }`}
                >
                  <span>{kw.term}</span>
                  <span className="text-[10px] opacity-75">({(kw.score || 0).toFixed(2)})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Search Term Results View */}
          {searchResults && (
            <div className="rounded-xl border border-primary-200 dark:border-primary-900 bg-primary-50/20 dark:bg-primary-950/10 p-6 shadow-sm">
              <h3 className="font-bold text-sm text-primary-900 dark:text-primary-300 mb-2">
                Document Passages for: <span className="underline">{selectedTerm}</span>
              </h3>
              <div className="space-y-3">
                {(searchResults.passages || []).map((p, idx) => (
                  <div key={idx} className="rounded-lg bg-white dark:bg-surface-darkCard p-3 text-xs border border-slate-200 dark:border-surface-darkBorder leading-relaxed">
                    <div className="flex items-center justify-between text-slate-400 mb-1">
                      <span className="font-semibold text-primary-600">Page {p.page_start}</span>
                      <span>Score: {(p.score || 0).toFixed(2)}</span>
                    </div>
                    <p className="text-slate-800 dark:text-slate-200">{p.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* LDA Topics & KMeans Clusters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">
                Latent Dirichlet Allocation (LDA) Topics
              </h3>
              <div className="space-y-3">
                {(topicsData?.lda_topics || []).map((tp, i) => (
                  <div key={i} className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-3 text-xs">
                    <p className="font-bold text-primary-700 dark:text-primary-400 mb-1">
                      Topic #{i + 1}
                    </p>
                    <p className="text-slate-600 dark:text-slate-300 font-mono">
                      {tp.words.join(', ')}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">
                KMeans Semantic Chunk Clusters
              </h3>
              <div className="space-y-3">
                {(topicsData?.clusters || []).map((cl, i) => (
                  <div key={i} className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-3 text-xs">
                    <p className="font-bold text-indigo-700 dark:text-indigo-400 mb-1">
                      Cluster {cl.cluster_id}: {cl.label}
                    </p>
                    <p className="text-slate-500">{cl.chunk_count} chunks assigned</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
