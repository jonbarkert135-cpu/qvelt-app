import { ChatShell } from "../components/chat-shell";
import { getPreferences } from "../lib/preferences";
import { messages } from "../lib/messages";

export default async function Page() {
  const preferences = await getPreferences();
  return <ChatShell {...preferences} t={messages[preferences.locale]} />;
}
