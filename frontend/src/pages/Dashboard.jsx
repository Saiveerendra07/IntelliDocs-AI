import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  MessageSquare,
  Award,
  TrendingUp,
  Upload,
  ArrowRight,
  Clock,
  AlertTriangle,
  Brain,
  Layers,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';
import { analyticsApi } from '../api/analytics';
import { documentsApi } from '../api/documents';

export const Dashboard = () => {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [recentDocs, setRecentDocs] = useState([]);
  const [weakTopics, setWeakTopics] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        const [statsData, docsData, weakData, activityData] = await Promise.allSettled([
          analyticsApi.getOverview(),
          documentsApi.list({ limit: 5 }),
          analyticsApi.getWeakTopics(),
          analyticsApi.getActivity(),
        ]);

        if (statsData.status === 'fulfilled') setOverview(statsData.value);
        if (docsData.status === 'fulfilled') setRecentDocs(docsData.value.items || []);
        if (weakData.status === 'fulfilled') setWeakTopics(weakData.value || []);
        if (activityData.status === 'fulfilled') setActivity(activityData.value || []);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ready':
      case 'processed':
        return <Badge variant="success">Processed ✓</Badge>;
      case 'processing':
      case 'extracting':
      case 'ocr':
        return <Badge variant="warning">Processing...</Badge>;
      case 'failed':
        return <Badge variant="danger">Failed</Badge>;
      default:
        return <Badge variant="neutral">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-2xl bg-gradient-to-r from-primary-700 via-primary-600 to-indigo-800 p-6 md:p-8 text-white shadow-sm">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/90 border border-white/20 mb-2">
            <Sparkles className="h-3.5 w-3.5" />
            Active Session
          </span>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Welcome back, {user?.full_name || 'Student'}!
          </h1>
          <p className="mt-1 text-sm text-white/80 max-w-xl">
            Track your document intelligence, explore NLP extraction, and challenge yourself with generated quizzes.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-primary-700 shadow-md hover:bg-slate-50 transition-colors"
          >
            <Upload className="h-4 w-4" />
            <span>Upload Document</span>
          </Link>
        </div>
      </div>

      {/* Four Authoritative Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Documents Processed"
          value={overview?.documents_count ?? (loading ? '...' : 0)}
          subtitle={`${overview?.total_pages ?? 0} total pages parsed`}
          icon={FileText}
          color="primary"
        />
        <StatCard
          title="Questions Asked (RAG)"
          value={overview?.questions_asked ?? (loading ? '...' : 0)}
          subtitle="Grounded citations"
          icon={MessageSquare}
          color="blue"
        />
        <StatCard
          title="Quizzes Completed"
          value={overview?.quizzes_completed ?? (loading ? '...' : 0)}
          subtitle="Adaptive evaluations"
          icon={Award}
          color="green"
        />
        <StatCard
          title="Average Score"
          value={overview?.average_score !== undefined ? `${overview.average_score}%` : (loading ? '...' : '0%')}
          subtitle="Overall mastery"
          icon={TrendingUp}
          color="amber"
        />
      </div>

      {/* Main Grid: Recent Documents & Learning Progress */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column (2 spans): Recent Documents */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">Recent Documents</h2>
            <Link
              to="/documents"
              className="text-xs font-semibold text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
            >
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard shadow-sm overflow-hidden">
            {recentDocs.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="No documents uploaded yet"
                description="Upload lecture slides, PDFs, or notes to begin automated analysis and quiz preparation."
                actionLabel="Upload First Document"
                onAction={() => window.location.href = '/upload'}
              />
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-surface-darkBorder">
                {recentDocs.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-400">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <Link
                          to={`/documents/${doc.id}`}
                          className="font-medium text-sm text-slate-900 dark:text-white hover:text-primary-600 dark:hover:text-primary-400 truncate block"
                        >
                          {doc.original_filename}
                        </Link>
                        <div className="flex items-center gap-2 mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                          <span>{doc.page_count || 1} pages</span>
                          <span>•</span>
                          <span>{(doc.file_size / (1024 * 1024)).toFixed(2)} MB</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {getStatusBadge(doc.status)}
                      <Link
                        to={`/documents/${doc.id}`}
                        className="rounded-lg p-1.5 text-slate-400 hover:text-primary-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Weak Topics Widget */}
          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">Targeted Practice Needed</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">Topics with accuracy under 60%</p>
              </div>
            </div>

            {weakTopics.length === 0 ? (
              <p className="text-xs text-slate-500 dark:text-slate-400 italic">
                No weak topics detected yet! Complete quizzes to identify areas for improvement.
              </p>
            ) : (
              <div className="space-y-3">
                {weakTopics.slice(0, 3).map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between rounded-lg bg-slate-50 dark:bg-slate-800/40 p-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900 dark:text-white">{item.topic}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.attempts} attempts • {item.accuracy}% accuracy</p>
                    </div>
                    <Link
                      to={`/questions?topic=${encodeURIComponent(item.topic)}`}
                      className="rounded-lg bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-100 dark:bg-primary-950/60 dark:text-primary-300"
                    >
                      Practice
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column (1 span): Learning Progress & Activity */}
        <div className="space-y-6">
          {/* Authoritative Learning Progress Ring Card */}
          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">
              Learning Progress
            </h2>

            <div className="flex flex-col items-center justify-center py-4">
              {/* Circular Gauge Representation */}
              <div className="relative flex h-36 w-36 items-center justify-center rounded-full border-8 border-primary-100 dark:border-primary-950/60">
                <div
                  className="absolute inset-0 rounded-full border-8 border-primary-600 border-t-transparent -rotate-45"
                  style={{
                    clipPath: `polygon(0 0, 100% 0, 100% 100%, 0 100%)`,
                  }}
                />
                <div className="text-center">
                  <span className="text-3xl font-extrabold text-slate-900 dark:text-white">
                    {overview?.topics_mastered_percent ?? 0}%
                  </span>
                  <span className="block text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                    Mastery
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 divide-x divide-slate-100 dark:divide-surface-darkBorder border-t border-slate-100 dark:border-surface-darkBorder pt-4 text-center">
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Topics</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                  {overview?.topics_count ?? 0}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Quizzes</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                  {overview?.quizzes_completed ?? 0}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400">Cards</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">
                  {overview?.flashcards_count ?? 0}
                </p>
              </div>
            </div>
          </div>

          {/* Recent Activity Feed */}
          <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
            <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">
              Recent Activity
            </h2>

            {activity.length === 0 ? (
              <p className="text-xs text-slate-500 dark:text-slate-400 italic">
                No recent activity recorded.
              </p>
            ) : (
              <div className="space-y-4">
                {activity.slice(0, 5).map((act, idx) => (
                  <div key={idx} className="flex items-start gap-3 text-xs">
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300">
                      <Clock className="h-3 w-3" />
                    </div>
                    <div>
                      <p className="font-medium text-slate-800 dark:text-slate-200">{act.message || act.type}</p>
                      <p className="text-slate-400 mt-0.5">{act.created_at || 'Just now'}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
