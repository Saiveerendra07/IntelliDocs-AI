import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  FileText,
  Search,
  Upload,
  Trash2,
  Download,
  Brain,
  MessageSquare,
  FileSpreadsheet,
  ArrowRight,
  Filter,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';

export const DocumentLibrary = () => {
  const [documents, setDocuments] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const res = await documentsApi.list({ search, status: statusFilter !== 'all' ? statusFilter : undefined });
      setDocuments(res.items || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [search, statusFilter]);

  const handleDelete = async (id, name) => {
    if (window.confirm(`Are you sure you want to delete "${name}"? All associated summaries, chunks, vectors, and quizzes will be removed.`)) {
      try {
        await documentsApi.delete(id);
        setDocuments((prev) => prev.filter((d) => d.id !== id));
      } catch (err) {
        alert('Failed to delete document: ' + (err.response?.data?.error?.message || err.message));
      }
    }
  };

  const handleDownload = async (id, name) => {
    try {
      const blob = await documentsApi.downloadOriginal(id);
      const url = window.URL.createObjectURL(new Blob([blob]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', name);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
    } catch (err) {
      alert('Failed to download document: ' + err.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Document Library
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Browse, manage, and inspect all ingested lecture materials and papers.
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 transition-colors"
        >
          <Upload className="h-4 w-4" />
          <span>Upload Document</span>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by filename or title..."
            className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard pl-10 pr-4 py-2 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-primary-600 focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-sm text-slate-700 dark:text-slate-200 focus:border-primary-600 focus:outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="ready">Processed</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Document Grid / Table */}
      {documents.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No documents in library"
          description={search ? "No documents match your search criteria." : "You have not uploaded any documents yet."}
          actionLabel="Upload New Document"
          onAction={() => navigate('/upload')}
        />
      ) : (
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard shadow-sm overflow-hidden">
          <div className="divide-y divide-slate-100 dark:divide-surface-darkBorder">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-4 sm:p-5 gap-4 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
              >
                <div className="flex items-start gap-4 min-w-0">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400 mt-0.5">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <Link
                      to={`/documents/${doc.id}`}
                      className="text-base font-semibold text-slate-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400 truncate block"
                    >
                      {doc.original_filename}
                    </Link>
                    <div className="flex flex-wrap items-center gap-2.5 mt-1 text-xs text-slate-500 dark:text-slate-400">
                      <span>{doc.page_count || 1} pages</span>
                      <span>•</span>
                      <span>{(doc.file_size / (1024 * 1024)).toFixed(2)} MB</span>
                      <span>•</span>
                      <span>{doc.mime_type || 'Document'}</span>
                      {doc.is_scanned && (
                        <>
                          <span>•</span>
                          <span className="text-amber-600 font-medium">Scanned (OCR)</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Status and Action Buttons */}
                <div className="flex items-center gap-3 self-end sm:self-center">
                  {doc.status === 'ready' && <Badge variant="success">Processed ✓</Badge>}
                  {doc.status === 'processing' && <Badge variant="warning">Processing</Badge>}
                  {doc.status === 'failed' && <Badge variant="danger">Failed</Badge>}

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleDownload(doc.id, doc.original_filename)}
                      title="Download Original"
                      className="rounded-lg p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <Download className="h-4 w-4" />
                    </button>
                    <Link
                      to={`/documents/${doc.id}?tab=nlp`}
                      title="NLP Analysis"
                      className="rounded-lg p-2 text-slate-400 hover:text-primary-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <Brain className="h-4 w-4" />
                    </Link>
                    <Link
                      to={`/documents/${doc.id}?tab=summary`}
                      title="Summarize"
                      className="rounded-lg p-2 text-slate-400 hover:text-primary-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <FileSpreadsheet className="h-4 w-4" />
                    </Link>
                    <button
                      onClick={() => handleDelete(doc.id, doc.original_filename)}
                      title="Delete"
                      className="rounded-lg p-2 text-slate-400 hover:text-red-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                    <Link
                      to={`/documents/${doc.id}`}
                      className="rounded-lg bg-primary-50 dark:bg-primary-950/50 p-2 text-primary-600 hover:bg-primary-100 dark:hover:bg-primary-900/50"
                      title="Open Inspector"
                    >
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
