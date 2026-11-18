import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  ChevronLeft,
  ChevronRight,
  Brain,
  MessageSquare,
  FileSpreadsheet,
  HelpCircle,
  Download,
  Share2,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { Badge } from '../components/common/Badge';

export const DocumentDetails = () => {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview';
  const navigate = useNavigate();

  const [document, setDocument] = useState(null);
  const [pages, setPages] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSearch, setPageSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDoc = async () => {
      setLoading(true);
      try {
        const doc = await documentsApi.getById(id);
        setDocument(doc);
        const pagesRes = await documentsApi.getPages(id);
        setPages(pagesRes.items || pagesRes || []);
      } catch (err) {
        console.error('Failed to load document details:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDoc();
  }, [id]);

  const handleTabChange = (tab) => {
    setSearchParams({ tab });
  };

  const activePageData = pages.find((p) => p.page_number === currentPage) || pages[0];

  const filteredPageText = activePageData?.text || 'No text extracted on this page.';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/documents')}
            className="rounded-xl border border-slate-200 dark:border-surface-darkBorder p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900 dark:text-white truncate max-w-md">
                {document?.original_filename || 'Loading Document...'}
              </h1>
              {document && <Badge variant="success">Ready</Badge>}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {document?.page_count || 1} pages • {(document?.file_size / (1024 * 1024))?.toFixed(2)} MB
            </p>
          </div>
        </div>

        {/* Shortcuts */}
        <div className="flex items-center gap-2">
          <Link
            to={`/summaries?documentId=${id}`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <FileSpreadsheet className="h-3.5 w-3.5 text-primary-600" />
            Summarize
          </Link>
          <Link
            to={`/nlp?documentId=${id}`}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <Brain className="h-3.5 w-3.5 text-primary-600" />
            NLP
          </Link>
          <Link
            to={`/chat?documentId=${id}`}
            className="inline-flex items-center gap-1.5 rounded-xl bg-primary-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-primary-700"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Chat (RAG)
          </Link>
        </div>
      </div>

      {/* Segmented Tabs */}
      <div className="flex border-b border-slate-200 dark:border-surface-darkBorder space-x-6 text-sm font-medium">
        {[
          { key: 'overview', label: 'Overview' },
          { key: 'text', label: 'Extracted Text' },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`pb-3 transition-colors ${
              activeTab === tab.key
                ? 'border-b-2 border-primary-600 text-primary-600 dark:text-primary-400 font-semibold'
                : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Contents */}
      {activeTab === 'overview' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h2 className="text-base font-bold text-slate-900 dark:text-white mb-3">
                Document Summary & Metadata
              </h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">File Type</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {document?.mime_type || 'Unknown'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">Language</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {document?.language || 'English'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">OCR Applied</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {document?.is_scanned ? 'Yes (Tesseract)' : 'No (Native Text)'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">Pages</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {document?.page_count || 1}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">File Size</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {((document?.file_size || 0) / (1024 * 1024)).toFixed(2)} MB
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 uppercase tracking-wider font-medium">Uploaded At</p>
                  <p className="text-sm font-semibold text-slate-800 dark:text-white mt-1">
                    {document?.created_at ? new Date(document.created_at).toLocaleDateString() : 'N/A'}
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Actions Card */}
            <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
              <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">
                Available NLP Actions
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Link
                  to={`/summaries?documentId=${id}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-surface-darkBorder p-3.5 hover:border-primary-500 hover:bg-primary-50/30 transition-all"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-100 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300">
                    <FileSpreadsheet className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                      Generate Summary
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Extractive (TextRank) & Abstractive
                    </p>
                  </div>
                </Link>

                <Link
                  to={`/nlp?documentId=${id}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-surface-darkBorder p-3.5 hover:border-primary-500 hover:bg-primary-50/30 transition-all"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300">
                    <Brain className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                      NLP Analysis
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      POS, NER, Topics, N-grams
                    </p>
                  </div>
                </Link>

                <Link
                  to={`/questions?documentId=${id}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-surface-darkBorder p-3.5 hover:border-primary-500 hover:bg-primary-50/30 transition-all"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                    <HelpCircle className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                      Generate Exam Questions
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      MCQ, True/False, Short Answer
                    </p>
                  </div>
                </Link>

                <Link
                  to={`/chat?documentId=${id}`}
                  className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-surface-darkBorder p-3.5 hover:border-primary-500 hover:bg-primary-50/30 transition-all"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300">
                    <MessageSquare className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm text-slate-900 dark:text-white">
                      Ask Questions (RAG)
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Verbatim citations & explanation modes
                    </p>
                  </div>
                </Link>
              </div>
            </div>
          </div>

          {/* Right Column: First Page Snapshot / Preview */}
          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white mb-3">
              First Page Extract Preview
            </h3>
            <div className="rounded-lg bg-slate-50 dark:bg-slate-900/50 p-4 font-mono text-xs text-slate-600 dark:text-slate-300 max-h-96 overflow-y-auto leading-relaxed border border-slate-200/50 dark:border-surface-darkBorder">
              {pages[0]?.text ? pages[0].text.slice(0, 1000) + '...' : 'No preview available.'}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Extracted Text Inspector */}
      {activeTab === 'text' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white dark:bg-surface-darkCard p-4 rounded-xl border border-slate-200 dark:border-surface-darkBorder">
            {/* Page navigation */}
            <div className="flex items-center gap-3">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                className="rounded-lg p-1.5 border border-slate-300 dark:border-surface-darkBorder disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-sm font-semibold text-slate-800 dark:text-white">
                Page {currentPage} of {pages.length || 1}
              </span>
              <button
                disabled={currentPage >= (pages.length || 1)}
                onClick={() => setCurrentPage((p) => Math.min(p + 1, pages.length || 1))}
                className="rounded-lg p-1.5 border border-slate-300 dark:border-surface-darkBorder disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {/* In-page search */}
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={pageSearch}
                onChange={(e) => setPageSearch(e.target.value)}
                placeholder="Find text on page..."
                className="w-full rounded-lg border border-slate-300 dark:border-surface-darkBorder bg-slate-50 dark:bg-slate-900/50 pl-9 pr-3 py-1.5 text-xs text-slate-800 dark:text-white placeholder:text-slate-400 focus:outline-none"
              />
            </div>
          </div>

          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <div className="font-mono text-xs leading-relaxed text-slate-800 dark:text-slate-200 whitespace-pre-wrap select-text">
              {filteredPageText}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
