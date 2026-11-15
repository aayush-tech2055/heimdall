"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { RoleGate } from "@/components/auth/role-gate";
import { PageHeader } from "@/components/shell/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, apiBlobUrl, ApiError } from "@/lib/api";
import type { Asset, AssetKind, Me } from "@/types/api";

const KINDS: { value: AssetKind; label: string }[] = [
  { value: "logo", label: "Logo" },
  { value: "disclaimer", label: "Disclaimer" },
  { value: "product_description", label: "Product description" },
  { value: "template", label: "Template" },
  { value: "other", label: "Other" },
];

function Thumb({ asset }: { asset: Asset }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!asset.has_file) return;
    let made: string | null = null;
    apiBlobUrl(`/assets/${asset.id}/file`)
      .then((u) => setUrl((made = u)))
      .catch(() => setUrl(null));
    return () => {
      if (made) URL.revokeObjectURL(made);
    };
  }, [asset]);
  if (!url) return null;
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt={asset.description || asset.name}
      className="h-16 w-auto rounded border bg-white p-1"
    />
  );
}

function Library({ me }: { me: Me }) {
  const [assets, setAssets] = useState<Asset[] | null>(null);
  const [kind, setKind] = useState<AssetKind>("logo");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const base = `/brands/${me.brand_id}/assets`;

  const load = useCallback(async () => {
    try {
      setAssets(await api<Asset[]>(base));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load assets");
    }
  }, [base]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("kind", kind);
    form.append("name", name);
    form.append("description", description);
    if (text.trim()) form.append("text_content", text);
    if (file) form.append("file", file);
    try {
      await api(base, { form });
      setName("");
      setDescription("");
      setText("");
      setFile(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add the asset");
    } finally {
      setBusy(false);
    }
  }

  async function remove(asset: Asset) {
    try {
      await api(`${base}/${asset.id}`, { method: "DELETE" });
      setAssets((prev) => (prev ?? []).filter((a) => a.id !== asset.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Asset library"
        description="Approved logos, disclaimers and product copy. Image checks read their descriptions, and missing disclaimers are fixed with the approved text."
      />
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Add an asset</h2>
          </CardTitle>
          <CardDescription>
            Give a file (PNG or JPEG), a description, the approved text, or all
            three.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={add} className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="asset-kind">Kind</Label>
              <Select
                value={kind}
                onValueChange={(v) => setKind(v as AssetKind)}
              >
                <SelectTrigger id="asset-kind" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k.value} value={k.value}>
                      {k.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="asset-name">Name</Label>
              <Input
                id="asset-name"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="asset-desc">
                Description (what the image checker should know)
              </Label>
              <Textarea
                id="asset-desc"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="e.g. Indigo wordmark on white; never stretched or recoloured"
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="asset-text">
                Approved text (for disclaimers and product copy)
              </Label>
              <Textarea
                id="asset-text"
                rows={2}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="asset-file">Image file (optional)</Label>
              <Input
                id="asset-file"
                type="file"
                accept="image/png,image/jpeg"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={busy || !name.trim()}>
                {busy ? (
                  <Loader2 className="animate-spin" aria-hidden />
                ) : (
                  <Plus aria-hidden />
                )}{" "}
                Add asset
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
      {error && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {assets === null ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : assets.length === 0 ? (
        <p className="text-muted-foreground">No assets yet.</p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {assets.map((a) => (
            <li key={a.id} className="bg-card flex gap-3 rounded-lg border p-3">
              <Thumb asset={a} />
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{a.name}</span>
                  <Badge variant="secondary">
                    {KINDS.find((k) => k.value === a.kind)?.label}
                  </Badge>
                </div>
                {a.description && <p className="text-sm">{a.description}</p>}
                {a.text_content && (
                  <p className="bg-muted rounded p-1.5 text-sm">
                    “{a.text_content}”
                  </p>
                )}
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Delete ${a.name}`}
                onClick={() => remove(a)}
              >
                <Trash2 aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function AssetsPage() {
  return <RoleGate roles={["admin"]}>{(me) => <Library me={me} />}</RoleGate>;
}
