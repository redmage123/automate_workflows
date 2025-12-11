/**
 * Skeleton Loading Components
 *
 * WHAT: Placeholder components for content loading states.
 *
 * WHY: Better UX than spinners for content that has known structure.
 * Shows approximate layout while actual content loads.
 *
 * HOW: Gray animated placeholder shapes matching content dimensions.
 */

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton with animation.
 */
function SkeletonBase({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-gray-200 rounded ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

/**
 * Text line skeleton.
 */
export function SkeletonText({ className = '' }: SkeletonProps) {
  return <SkeletonBase className={`h-4 ${className}`} />;
}

/**
 * Heading skeleton.
 */
export function SkeletonHeading({ className = '' }: SkeletonProps) {
  return <SkeletonBase className={`h-6 ${className}`} />;
}

/**
 * Avatar/circle skeleton.
 */
export function SkeletonAvatar({
  className = '',
  size = 'md',
}: SkeletonProps & { size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
  };
  return (
    <SkeletonBase className={`${sizeClasses[size]} rounded-full ${className}`} />
  );
}

/**
 * Card skeleton.
 */
export function SkeletonCard({ className = '' }: SkeletonProps) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      <SkeletonHeading className="w-3/4 mb-4" />
      <SkeletonText className="w-full mb-2" />
      <SkeletonText className="w-5/6 mb-2" />
      <SkeletonText className="w-4/6" />
    </div>
  );
}

/**
 * Table row skeleton.
 */
export function SkeletonTableRow({
  columns = 4,
  className = '',
}: SkeletonProps & { columns?: number }) {
  return (
    <tr className={className}>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-6 py-4">
          <SkeletonText className={`w-${i === 0 ? 'full' : '3/4'}`} />
        </td>
      ))}
    </tr>
  );
}

/**
 * Table skeleton.
 */
export function SkeletonTable({
  rows = 5,
  columns = 4,
  className = '',
}: SkeletonProps & { rows?: number; columns?: number }) {
  return (
    <div className={`overflow-hidden ${className}`}>
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-6 py-3">
                <SkeletonText className="w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonTableRow key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Stat card skeleton.
 */
export function SkeletonStat({ className = '' }: SkeletonProps) {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-6 ${className}`}>
      <div className="flex items-center">
        <SkeletonAvatar size="lg" />
        <div className="ml-4 flex-1">
          <SkeletonText className="w-20 mb-2" />
          <SkeletonHeading className="w-16" />
        </div>
      </div>
    </div>
  );
}

/**
 * Form skeleton.
 */
export function SkeletonForm({
  fields = 4,
  className = '',
}: SkeletonProps & { fields?: number }) {
  return (
    <div className={`space-y-6 ${className}`}>
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i}>
          <SkeletonText className="w-24 mb-2" />
          <SkeletonBase className="h-10 w-full" />
        </div>
      ))}
      <SkeletonBase className="h-10 w-32" />
    </div>
  );
}

export default SkeletonBase;
