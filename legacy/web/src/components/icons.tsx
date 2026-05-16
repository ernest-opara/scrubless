import type { SVGProps } from 'react'

// A small, consistent line-icon set. 16x16, stroke = currentColor.
type IconProps = SVGProps<SVGSVGElement>

function Svg({ children, ...props }: IconProps) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  )
}

export function IconSearch(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6.8" cy="6.8" r="4.3" />
      <path d="M10 10 14 14" />
    </Svg>
  )
}

export function IconPlay(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M5 3.4 12.2 8 5 12.6Z" fill="currentColor" stroke="none" />
    </Svg>
  )
}

export function IconClock(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 4.6V8l2.4 1.6" />
    </Svg>
  )
}

export function IconSpark(props: IconProps) {
  return (
    <Svg {...props}>
      <path
        d="M8 1.6 9.5 6.5 14.4 8 9.5 9.5 8 14.4 6.5 9.5 1.6 8 6.5 6.5Z"
        fill="currentColor"
        stroke="none"
      />
    </Svg>
  )
}

export function IconScissors(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="4" cy="4.6" r="2.1" />
      <circle cx="4" cy="11.4" r="2.1" />
      <path d="M5.9 5.7 14 11.4M5.9 10.3 14 4.6M8.4 8H8.5" />
    </Svg>
  )
}

export function IconLink(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6.6 9.4 9.4 6.6" />
      <path d="M7.4 4.4 8.9 2.9a2.4 2.4 0 0 1 3.4 3.4L10.8 7.8" />
      <path d="M8.6 11.6 7.1 13.1a2.4 2.4 0 0 1-3.4-3.4L5.2 8.2" />
    </Svg>
  )
}

export function IconUpload(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 10.6V3.2" />
      <path d="M5.2 6 8 3.2 10.8 6" />
      <path d="M3 10.6v1.4A1.6 1.6 0 0 0 4.6 13.6h6.8A1.6 1.6 0 0 0 13 12v-1.4" />
    </Svg>
  )
}

export function IconDownload(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M8 3.2v7.4" />
      <path d="M5.2 7.8 8 10.6 10.8 7.8" />
      <path d="M3 10.6v1.4A1.6 1.6 0 0 0 4.6 13.6h6.8A1.6 1.6 0 0 0 13 12v-1.4" />
    </Svg>
  )
}
