import { humanizeKey } from './format.js'

function TargetingNode({ node }) {
  if (!node) return null

  if (Array.isArray(node)) {
    return (
      <>
        {node.map((child, i) => <TargetingNode key={i} node={child} />)}
      </>
    )
  }

  if (node.and) {
    return (
      <div className="targeting-group">
        <span className="targeting-op">All of</span>
        <div className="targeting-children">
          <TargetingNode node={node.and} />
        </div>
      </div>
    )
  }

  if (node.or) {
    return (
      <div className="targeting-group">
        <span className="targeting-op">Any of</span>
        <div className="targeting-children">
          <TargetingNode node={node.or} />
        </div>
      </div>
    )
  }

  // Facet map: { 'urn:li:adTargetingFacet:xxx': [...] }
  return (
    <>
      {Object.entries(node).map(([facetKey, values]) => (
        <div className="targeting-facet" key={facetKey}>
          <span className="targeting-facet-name">{humanizeKey(facetKey.split(':').pop())}</span>
          <div className="targeting-tags">
            {(Array.isArray(values) ? values : [values]).map((v, i) => (
              <span className="targeting-tag" key={i}>
                {typeof v === 'object' && v !== null ? (v.resolved_name || v.urn) : String(v)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </>
  )
}

export default function TargetingSection({ targeting }) {
  if (!targeting) return null

  return (
    <section className="targeting">
      <h3>Targeting</h3>
      <div className="targeting-grid">
        {targeting.include && (
          <div className="targeting-block">
            <h4>Include</h4>
            <TargetingNode node={targeting.include} />
          </div>
        )}
        {targeting.exclude && (
          <div className="targeting-block">
            <h4>Exclude</h4>
            <TargetingNode node={targeting.exclude} />
          </div>
        )}
      </div>
    </section>
  )
}
