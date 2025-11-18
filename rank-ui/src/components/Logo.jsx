// ==============================
// File: src/components/Logo.jsx
// Icon-only logo used in Navbar
// ==============================

export default function Logo({ className = "" }) {
  return (
    <div
      className={
        "flex items-center justify-center rounded-xl bg-indigo-600 text-xs font-semibold " +
        (className || "w-8 h-8")
      }
    >
      SR
    </div>
  );
}


// // src/components/Logo.jsx
// import { APP_NAME } from "../brand";

// export default function Logo({ className = "", withText = true }) {
//   return (
//     <div className={`flex items-center gap-2 ${className}`}>
//       {/* Mark */}
//       <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
//         <defs>
//           <linearGradient id="g" x1="0" x2="1" y1="1" y2="0">
//             <stop offset="0%" stopColor="#6366f1" />
//             <stop offset="100%" stopColor="#a78bfa" />
//           </linearGradient>
//         </defs>
//         <rect x="2" y="2" width="28" height="28" rx="7" fill="url(#g)"/>
//         <path d="M9 19l4-6 3 4 4-7 3 5" stroke="white" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
//       </svg>
//       {/* Wordmark */}
//       {withText && (
//         <span className="font-extrabold tracking-tight">
//           {APP_NAME}
//         </span>
//       )}
//     </div>
//   );
// }