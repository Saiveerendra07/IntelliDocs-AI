import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  X,
  File,
  ArrowRight,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { Badge } from '../components/common/Badge';

export const Upload = () => {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (newFiles) => {
    const validFiles = newFiles.map((file) => ({
      file,
      name: file.name,
      size: (file.size / (1024 * 1024)).toFixed(2) + ' MB',
      progress: 0,
      status: 'pending', // pending, uploading, ready, failed
      id: null,
      error: null,
    }));
    setFiles((prev) => [...prev, ...validFiles]);
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, idx) => idx !== index));
  };

  const uploadFileItem = async (item, index) => {
    const formData = new FormData();
    formData.append('file', item.file);

    setFiles((prev) =>
      prev.map((f, i) => (i === index ? { ...f, status: 'uploading', progress: 10 } : f))
    );

    try {
      const response = await documentsApi.upload(formData, (percent) => {
        setFiles((prev) =>
          prev.map((f, i) => (i === index ? { ...f, progress: Math.max(percent, 20) } : f))
        );
      });

      const docId = response.id;
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index ? { ...f, id: docId, progress: 60, status: 'processing' } : f
        )
      );

      // Poll status until ready or failed
      pollStatus(docId, index);
    } catch (err) {
      console.error('Upload failed:', err);
      setFiles((prev) =>
        prev.map((f, i) =>
          i === index
            ? { ...f, status: 'failed', error: err.response?.data?.error?.message || 'Upload failed' }
            : f
        )
      );
    }
  };

  const pollStatus = (docId, index) => {
    const interval = setInterval(async () => {
      try {
        const res = await documentsApi.getStatus(docId);
        if (res.status === 'ready') {
          clearInterval(interval);
          setFiles((prev) =>
            prev.map((f, i) =>
              i === index ? { ...f, status: 'ready', progress: 100 } : f
            )
          );
        } else if (res.status === 'failed') {
          clearInterval(interval);
          setFiles((prev) =>
            prev.map((f, i) =>
              i === index ? { ...f, status: 'failed', error: res.error_message } : f
            )
          );
        } else {
          setFiles((prev) =>
            prev.map((f, i) =>
              i === index
                ? {
                    ...f,
                    progress: Math.min(
                      Math.round((res.processing_progress || 0.7) * 100),
                      95
                    ),
                  }
                : f
            )
          );
        }
      } catch (e) {
        clearInterval(interval);
      }
    }, 1500);
  };

  const startAllUploads = async () => {
    setUploading(true);
    for (let i = 0; i < files.length; i++) {
      if (files[i].status === 'pending') {
        await uploadFileItem(files[i], i);
      }
    }
    setUploading(false);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Document Upload & Processing
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Upload PDFs, slides, documents, or images. The platform will automatically parse, apply OCR, extract sections, and index chunks into the local vector database.
        </p>
      </div>

      {/* Authoritative Large Dashed Drag-and-Drop Zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
          dragActive
            ? 'border-primary-600 bg-primary-50/60 dark:bg-primary-950/20'
            : 'border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard hover:border-primary-500 dark:hover:border-primary-500'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleChange}
          accept=".pdf,.docx,.pptx,.txt,.md,.csv,.png,.jpg,.jpeg,.webp"
          className="hidden"
        />
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-50 text-primary-600 dark:bg-primary-950/60 dark:text-primary-400 mb-4 shadow-sm">
          <UploadCloud className="h-8 w-8" />
        </div>
        <h3 className="text-lg font-bold text-slate-900 dark:text-white">
          Drag & drop files here, or click to browse
        </h3>
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 max-w-md">
          Supported formats: PDF (digital & scanned OCR), DOCX, PPTX, TXT, MD, CSV, PNG, JPG (Max 50 MB per file)
        </p>
        <button
          type="button"
          className="mt-6 rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 transition-colors"
        >
          Browse Files
        </button>
      </div>

      {/* File Rows & Real-Time Progress */}
      {files.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 dark:text-white">
              Selected Files ({files.length})
            </h2>
            <button
              onClick={startAllUploads}
              disabled={uploading || files.every((f) => f.status === 'ready')}
              className="rounded-xl bg-primary-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 disabled:opacity-50 transition-colors"
            >
              {uploading ? 'Processing Files...' : 'Start Ingestion'}
            </button>
          </div>

          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard divide-y divide-slate-100 dark:divide-surface-darkBorder shadow-sm overflow-hidden">
            {files.map((file, idx) => (
              <div key={idx} className="p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400">
                      <File className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-900 dark:text-white truncate">
                        {file.name}
                      </p>
                      <p className="text-xs text-slate-400">{file.size}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    {file.status === 'ready' && (
                      <Badge variant="success">Processed ✓</Badge>
                    )}
                    {file.status === 'processing' && (
                      <Badge variant="warning">
                        Processing {file.progress}%
                      </Badge>
                    )}
                    {file.status === 'uploading' && (
                      <Badge variant="info">
                        Uploading {file.progress}%
                      </Badge>
                    )}
                    {file.status === 'failed' && (
                      <Badge variant="danger">Failed</Badge>
                    )}
                    {file.status === 'pending' && (
                      <Badge variant="neutral">Pending</Badge>
                    )}

                    {file.status === 'ready' ? (
                      <button
                        onClick={() => navigate(`/documents/${file.id}`)}
                        className="rounded-lg p-1.5 text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-950/40"
                        title="View Details"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </button>
                    ) : (
                      <button
                        onClick={() => removeFile(idx)}
                        className="rounded-lg p-1.5 text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                        title="Remove"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Linear Progress Bar */}
                {file.status !== 'pending' && file.status !== 'ready' && (
                  <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-primary-600 h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${file.progress}%` }}
                    />
                  </div>
                )}

                {file.error && (
                  <p className="text-xs text-red-500 dark:text-red-400 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    {file.error}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
