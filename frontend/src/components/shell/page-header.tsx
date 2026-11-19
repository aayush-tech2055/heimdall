export function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-6">
      <h1 className="hd-gradient-text text-3xl font-bold tracking-tight">
        {title}
      </h1>
      <div
        aria-hidden
        className="mt-2 h-1 w-14 rounded-full bg-gradient-to-r from-black via-indigo-500 to-amber-400"
      />
      <p className="text-muted-foreground mt-3">{description}</p>
    </div>
  );
}
