import { OperatorFrame } from "@/components/OperatorFrame";

export default function OperatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <OperatorFrame>{children}</OperatorFrame>;
}
