import React from "react";
import { theme } from "../theme";

/** Mono uppercase eyebrow label — used in every titled scene. */
export const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = theme.accent,
}) => (
  <p
    style={{
      fontFamily: theme.fontMono,
      fontSize: 18,
      letterSpacing: "0.16em",
      textTransform: "uppercase",
      color,
      fontWeight: 500,
      margin: 0,
    }}
  >
    <span style={{ color: theme.fgFaint, marginRight: 10 }}>——</span>
    {children}
  </p>
);
