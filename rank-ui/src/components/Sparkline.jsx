// src/components/Sparkline.jsx
// Small, dependency-free SVG sparkline
export default function Sparkline({
    data = [],
    width = 120,
    height = 32,
    strokeWidth = 2,
    className = "",
  }) {
    if (!data?.length) {
      return <div className={`w-[${width}px] h-[${height}px] bg-slate-800/40 rounded ${className}`} />;
    }
  
    // Normalize to 0..1
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * (width - 2) + 1;
      const y = height - 1 - ((v - min) / range) * (height - 2);
      return [x, y];
    });
  
    const d = points.reduce(
      (acc, [x, y], i) => (i === 0 ? `M${x},${y}` : acc + ` L${x},${y}`),
      ""
    );
  
    const up = data[data.length - 1] >= data[0];
  
    return (
      <svg width={width} height={height} className={className}>
        {/* baseline */}
        <line x1="1" y1={height - 1} x2={width - 1} y2={height - 1} className="stroke-slate-700" strokeWidth="1" />
        {/* path */}
        <path d={d} fill="none" strokeWidth={strokeWidth}
          className={up ? "stroke-emerald-400" : "stroke-rose-400"} />
        {/* last dot */}
        {points.length ? (
          <circle
            cx={points[points.length - 1][0]}
            cy={points[points.length - 1][1]}
            r="2.5"
            className={up ? "fill-emerald-400" : "fill-rose-400"}
          />
        ) : null}
      </svg>
    );
  }
  