import React from "react";

/** macOS-y arrow cursor SVG, used for synthetic UI demo scenes. */
export const Cursor: React.FC<{ x: number; y: number; size?: number }> = ({
  x,
  y,
  size = 28,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 18 18"
      style={{
        position: "absolute",
        left: x,
        top: y,
        pointerEvents: "none",
        filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.25))",
      }}
    >
      <path
        d="M2 2 L2 14 L6 11 L8 16 L10 15 L8 10 L13 10 Z"
        fill="#fff"
        stroke="#000"
        strokeWidth={0.8}
        strokeLinejoin="round"
      />
    </svg>
  );
};
