import { UserMenu } from "./user-menu";

export function Header({ title, description }: { title: string; description?: string }) {
  return (
    <header className="flex items-center justify-between border-b border-ink-100 bg-white px-6 py-4">
      <div>
        <h1 className="text-base font-semibold text-ink-900">{title}</h1>
        {description && <p className="text-sm text-ink-500">{description}</p>}
      </div>
      <UserMenu />
    </header>
  );
}
