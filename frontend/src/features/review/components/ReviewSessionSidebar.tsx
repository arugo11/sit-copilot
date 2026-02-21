export function ReviewSessionSidebar({ sessionId }: { sessionId: string }) {
  return (
    <div className="space-y-4">
      <section className="card p-3 space-y-2">
        <h2 className="font-semibold">講義情報</h2>
        <p className="text-sm text-fg-secondary">機械学習入門 / Session: {sessionId}</p>
        <p className="text-sm">主要トピック: 過学習, 正則化, 検証手法</p>
      </section>
      <section className="card p-3 space-y-2">
        <h2 className="font-semibold">要約</h2>
        <p className="text-sm text-fg-secondary">
          講義後QAでは根拠チップから元ソースへ同期できます。
        </p>
      </section>
    </div>
  )
}
