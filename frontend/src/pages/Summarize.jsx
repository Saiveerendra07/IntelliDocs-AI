import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  FileSpreadsheet,
  Brain,
  Sparkles,
  BookOpen,
  CheckCircle,
  Copy,
  Download,
  BarChart2,
  ListOrdered,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { summariesApi } from '../api/summaries';
import { Badge } from '../components/common/Badge';

export const Summarize = () => {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get('documentId') || '';

  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(initialDocId);
  const [activeTab, setActiveTab] = useState('extractive'); // 'extractive' | 'abstractive' | 'compare'
  const [length, setLength] = useState('medium'); // 'short' | 'medium' | 'detailed'
  const [mode, setMode] = useState('standard'); // 'standard' | 'bullet' | 'chapter' | 'exam'
  const [extractiveMethod, setExtractiveMethod] = useState('textrank'); // 'frequency' | 'tfidf' | 'textrank'
  
  const [summaryData, setSummaryData] = useState(null);
  const [comparisonData, setComparisonData] = useState(null);
  const [loading, setLoading] = useState(false);

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

  const handleGenerate = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    try {
      if (activeTab === 'compare') {
        const comp = await summariesApi.compare(selectedDocId, extractiveMethod);
        setComparisonData(comp);
      } else {
        const res = await summariesApi.generate(selectedDocId, {
          method: activeTab === 'extractive' ? extractiveMethod : 'abstractive',
          length,
          mode,
        });
        setSummaryData(res);
      }
    } catch (err) {
      console.error('Summary generation failed:', err);
      alert('Summary generation error: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const selectedDoc = documents.find((d) => d.id === selectedDocId);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Document Summarization
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Compute real extractive summaries (Frequency, TF-IDF, TextRank) and neural abstractive condensations.
          </p>
        </div>

        {/* Document Selector Dropdown */}
        <div className="flex items-center gap-2">
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            className="rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3.5 py-2 text-sm font-medium text-slate-800 dark:text-white focus:border-primary-600 focus:outline-none"
          >
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.original_filename} ({d.page_count || 1} pgs)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Configuration Header Card */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm space-y-4">
        {/* Method Tabs */}
        <div className="flex border-b border-slate-200 dark:border-surface-darkBorder space-x-6 text-sm font-semibold">
          {[
            { key: 'extractive', label: 'Extractive Summary' },
            { key: 'abstractive', label: 'Abstractive Summary' },
            { key: 'compare', label: 'Extractive vs. Abstractive Comparison' },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={`pb-3 transition-colors ${
                activeTab === t.key
                  ? 'border-b-2 border-primary-600 text-primary-600 dark:text-primary-400'
                  : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Controls Row */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            {/* Extractive Algorithm Selector */}
            {activeTab !== 'abstractive' && (
              <div>
                <label className="block text-slate-400 font-semibold mb-1 uppercase tracking-wider">
                  Algorithm
                </label>
                <select
                  value={extractiveMethod}
                  onChange={(e) => setExtractiveMethod(e.target.value)}
                  className="rounded-lg border border-slate-300 dark:border-surface-darkBorder bg-slate-50 dark:bg-slate-900/50 px-3 py-1.5 text-xs text-slate-800 dark:text-white font-medium focus:outline-none"
                >
                  <option value="textrank">TextRank (Graph PageRank)</option>
                  <option value="tfidf">TF-IDF Sentence Ranking</option>
                  <option value="frequency">Word Frequency Sentence Scoring</option>
                </select>
              </div>
            )}

            {/* Length Selector */}
            <div>
              <label className="block text-slate-400 font-semibold mb-1 uppercase tracking-wider">
                Length
              </label>
              <div className="inline-flex rounded-lg border border-slate-300 dark:border-surface-darkBorder p-0.5 bg-slate-50 dark:bg-slate-900/50">
                {['short', 'medium', 'detailed'].map((l) => (
                  <button
                    key={l}
                    onClick={() => setLength(l)}
                    className={`rounded-md px-2.5 py-1 text-xs font-semibold capitalize transition-all ${
                      length === l
                        ? 'bg-white dark:bg-surface-darkCard text-primary-600 dark:text-primary-400 shadow-sm'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                    }`}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Mode Selector */}
            <div>
              <label className="block text-slate-400 font-semibold mb-1 uppercase tracking-wider">
                Mode
              </label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="rounded-lg border border-slate-300 dark:border-surface-darkBorder bg-slate-50 dark:bg-slate-900/50 px-3 py-1.5 text-xs text-slate-800 dark:text-white font-medium focus:outline-none"
              >
                <option value="standard">Standard Paragraphs</option>
                <option value="bullet">Bullet Points Mode</option>
                <option value="chapter">Chapter-wise Mode</option>
                <option value="exam">Exam-Oriented Mode</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !selectedDocId}
            className="flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50 transition-all"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            <span>Generate Summary</span>
          </button>
        </div>
      </div>

      {/* Comparison View */}
      {activeTab === 'compare' && comparisonData && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 text-center">
              <p className="text-xs text-slate-400 uppercase font-semibold">ROUGE-1 Overlap</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                {(comparisonData.rouge?.rouge1 * 100)?.toFixed(1) || '0.0'}%
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 text-center">
              <p className="text-xs text-slate-400 uppercase font-semibold">ROUGE-L (LCS)</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                {(comparisonData.rouge?.rougeL * 100)?.toFixed(1) || '0.0'}%
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 text-center">
              <p className="text-xs text-slate-400 uppercase font-semibold">Compression Ratio</p>
              <p className="text-xl font-bold text-primary-600 dark:text-primary-400 mt-1">
                {comparisonData.compression_ratio?.toFixed(1) || '0.0'}x
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-base text-slate-900 dark:text-white">
                  Extractive Summary ({comparisonData.extractive_method})
                </h3>
                <Badge variant="primary">Extractive</Badge>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                {comparisonData.extractive_text}
              </p>
            </div>

            <div className="rounded-xl border border-slate-200 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-base text-slate-900 dark:text-white">
                  Abstractive Summary (DistilBART)
                </h3>
                <Badge variant="info">Abstractive</Badge>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                {comparisonData.abstractive_text}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Main Single Summary Panels */}
      {activeTab !== 'compare' && summaryData && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Summary Panel (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100 dark:border-surface-darkBorder">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                    Generated Summary
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Method: {summaryData.method} • Length: {summaryData.length} • Mode: {summaryData.mode}
                  </p>
                </div>
                <Badge variant="success">Computed Live</Badge>
              </div>

              <div className="prose dark:prose-invert max-w-none text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap">
                {summaryData.content}
              </div>
            </div>

            {/* Main Points Card */}
            {summaryData.key_points && summaryData.key_points.length > 0 && (
              <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
                <h3 className="font-bold text-base text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-emerald-500" />
                  Main Points
                </h3>
                <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
                  {summaryData.key_points.map((pt, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-primary-600 font-bold">•</span>
                      <span>{pt}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Right Column: Key Takeaways & Definitions */}
          <div className="space-y-6">
            {/* Key Takeaways */}
            <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h3 className="font-bold text-base text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary-600" />
                Key Takeaways
              </h3>
              <div className="space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
                {(summaryData.takeaways || []).length > 0 ? (
                  summaryData.takeaways.map((t, i) => (
                    <div key={i} className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 border-l-2 border-primary-600">
                      {t}
                    </div>
                  ))
                ) : (
                  <p className="italic text-slate-400">Key takeaways computed with TextRank PageRank.</p>
                )}
              </div>
            </div>

            {/* Important Definitions */}
            <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h3 className="font-bold text-base text-slate-900 dark:text-white mb-3 flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-indigo-600" />
                Important Definitions
              </h3>
              <div className="space-y-2">
                {(summaryData.definitions || []).map((def, i) => (
                  <div key={i} className="rounded-lg bg-slate-50 dark:bg-slate-800/40 p-2.5 text-xs">
                    <span className="font-semibold text-slate-900 dark:text-white">{def.term}: </span>
                    <span className="text-slate-600 dark:text-slate-300">{def.definition}</span>
                    {def.page && (
                      <span className="text-[10px] text-primary-600 font-bold ml-1.5">[Page {def.page}]</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Empty State before generation */}
      {!summaryData && !comparisonData && !loading && (
        <div className="rounded-xl border-2 border-dashed border-slate-200 dark:border-surface-darkBorder p-12 text-center bg-white/40 dark:bg-surface-darkCard/20">
          <FileSpreadsheet className="h-12 w-12 text-primary-500 mx-auto mb-3" />
          <h3 className="text-base font-bold text-slate-800 dark:text-white">
            Ready to summarize document
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
            Select an extractive algorithm (Frequency, TF-IDF, or TextRank) or abstractive summarization, adjust the length and mode, and click "Generate Summary".
          </p>
        </div>
      )}
    </div>
  );
};
