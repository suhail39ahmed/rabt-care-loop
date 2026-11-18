import { api } from "@/lib/api";
import { HomeView, type Demo } from "@/components/HomeView";

export default async function HomePage() {
  let demo: Demo | null = null;
  try {
    demo = await api<Demo>("/demo");
  } catch {
    demo = null;
  }
  return <HomeView demo={demo} />;
}
