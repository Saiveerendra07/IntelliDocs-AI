import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart3,
  Award,
  AlertTriangle,
  TrendingUp,
  Clock,
  BookOpen,
  ArrowRight,
  Flame,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';
import { analyticsApi } from '../api/analytics';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';

export const Analytics = () => {
  const [overview, setOverview] = useState(null);
  const [progress, setProgress] = useState([]);
  const [weakTopics, setWeakTopics] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [ov, pr, wt, ac] = await Promise.allSettled([
          analyticsApi.getOverview(),
          analyticsApi.getProgress(),
          analyticsApi.getWeakTopics(),
          analyticsApi.getActivity(),
        ]);
        if (ov.status === 'fulfilled') setOverview(ov.value);
        if (pr.status === 'fulfilled') setProgress(pr.value || []);
        if (wt.status === 'fulfilled') setWeakTopics(wt.value || []);
        if (ac.status === 'fulfilled') setActivity(ac.value || []);
      } catch (err) {
        console.error('Failed to load analytics:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Learning Analytics & Performance
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Aggregated learning metrics computed from database attempt records, tracking mastery and study streaks.
        </p>
      </div>

      {/* Top 4 Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Overall Mastery"
          value={overview?.average_score !== undefined ? `${overview.average_score}%` : '--'}
          subtitle="Cumulative quiz accuracy"
          icon={TrendingUp}
          color="primary"
        />
        <StatCard
          title="Quizzes Completed"
          value={overview?.quizzes_completed ?? 0}
          subtitle="Evaluated attempts"
          icon={Award}
          color="green"
        />
        <StatCard
          title="Study Streak"
          value={overview?.study_streak_days !== undefined ? `${overview.study_streak_days} Days` : '1 Day'}
          subtitle="Continuous study days"
          icon={Flame}
          color="amber"
        />
        <StatCard
          title="Flashcards Reviewed"
          value={overview?.flashcards_reviewed ?? 0}
          subtitle="Spaced repetition passes"
          icon={BookOpen}
          color="blue"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Score Trend Line Chart */}
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">
            Score Trend Over Time
          </h2>
          <div className="h-64 w-full">
            {progress.length === 0 ? (
              <div className="flex h-full items-center justify-center text-xs text-slate-400 italic">
                Take quizzes to see your historical performance trend.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={progress}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#5B3FD0"
                    strokeWidth={2.5}
                    dot={{ fill: '#5B3FD0' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Topic-Wise Accuracy Breakdown */}
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 dark:text-white mb-4">
            Topic-Wise Mastery Breakdown
          </h2>
          <div className="h-64 w-full">
            {(overview?.topic_performance || []).length === 0 ? (
              <div className="flex h-full items-center justify-center text-xs text-slate-400 italic">
                No topic data recorded yet.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={overview.topic_performance}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="topic" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="accuracy" fill="#10B981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Weak Topics Section */}
      <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            Weak-Topic Recommendations (Accuracy &lt; 60%)
          </h2>
        </div>

        {weakTopics.length === 0 ? (
          <p className="text-xs text-slate-400 italic">
            No weak topics detected! Your accuracy is consistently above 60% across tested subjects.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-100 dark:border-surface-darkBorder text-slate-400 uppercase font-semibold">
                <tr>
                  <th className="py-2.5">Topic</th>
                  <th className="py-2.5">Attempts</th>
                  <th className="py-2.5">Accuracy</th>
                  <th className="py-2.5">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-surface-darkBorder text-slate-700 dark:text-slate-300">
                {weakTopics.map((wt, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="py-3 font-medium text-slate-900 dark:text-white">{wt.topic}</td>
                    <td className="py-3">{wt.attempts} attempts</td>
                    <td className="py-3">
                      <span className="font-bold text-red-500">{wt.accuracy}%</span>
                    </td>
                    <td className="py-3">
                      <Link
                        to={`/questions?topic=${encodeURIComponent(wt.topic)}`}
                        className="inline-flex items-center gap-1 rounded-lg bg-primary-50 px-2.5 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-100 dark:bg-primary-950/60 dark:text-primary-300"
                      >
                        Practice Topic <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
