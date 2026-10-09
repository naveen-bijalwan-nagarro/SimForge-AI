import React, { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import DeckGL from "@deck.gl/react";
import { OrthographicView } from "@deck.gl/core";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import { healthColor } from "./viz";

/* ------------------------------------------------------------------ React Three Fiber world */
function layered(nodes, edges) {
  const parents = Object.fromEntries(nodes.map((n) => [n.id, []]));
  edges.forEach((e) => parents[e.target]?.push(e.source));
  const depth = {};
  const visit = (id, seen = new Set()) => {
    if (depth[id] != null) return depth[id];
    if (seen.has(id)) return 0;
    seen.add(id);
    depth[id] = parents[id].length ? 1 + Math.max(...parents[id].map((p) => visit(p, seen))) : 0;
    return depth[id];
  };
  nodes.forEach((n) => visit(n.id));
  const layers = {};
  nodes.forEach((n) => (layers[depth[n.id]] = [...(layers[depth[n.id]] || []), n.id]));
  const maxDepth = Math.max(...Object.keys(layers).map(Number));
  const pos = {};
  Object.entries(layers).forEach(([d, ids]) =>
    ids.forEach((id, i) => (pos[id] = [(Number(d) - maxDepth / 2) * 4.2, 0, (i - (ids.length - 1) / 2) * 3.6])),
  );
  return pos;
}

// Labels are drawn into a canvas texture and shown as sprites: no DOM overlay, no font download.
function Label({ text, sub, color, position }) {
  const texture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 320;
    c.height = 88;
    const g = c.getContext("2d");
    g.fillStyle = "rgba(15, 20, 38, 0.82)";
    g.beginPath();
    g.roundRect(4, 4, 312, 80, 14);
    g.fill();
    g.textAlign = "center";
    g.fillStyle = "#ffffff";
    g.font = "600 26px Inter, Segoe UI, Arial, sans-serif";
    g.fillText(text.length > 22 ? text.slice(0, 21) + "…" : text, 160, 38);
    g.fillStyle = color;
    g.font = "700 26px Inter, Segoe UI, Arial, sans-serif";
    g.fillText(sub, 160, 72);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [text, sub, color]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <sprite position={position} scale={[2.9, 0.8, 1]}>
      <spriteMaterial map={texture} transparent depthWrite={false} />
    </sprite>
  );
}

function Tower({ node, position, health, capacity, style, alert, onSelect }) {
  const glow = useRef();
  useFrame(({ clock }) => {
    if (glow.current) {
      const s = 1 + 0.25 * Math.sin(clock.elapsedTime * 5);
      glow.current.scale.set(s, s, 1);
      glow.current.material.opacity = 0.35 + 0.25 * Math.sin(clock.elapsedTime * 5);
    }
  });
  const color = healthColor(health);
  const height = 0.6 + capacity * 0.18;
  return (
    <group position={position} onClick={(e) => (e.stopPropagation(), onSelect?.(node))}>
      {style === "voxel" ? (
        Array.from({ length: Math.max(2, Math.round(height / 0.5)) }).map((_, i) => (
          <mesh key={i} position={[((i % 2) - 0.5) * 0.05, 0.25 + i * 0.5, 0]} castShadow>
            <boxGeometry args={[0.95, 0.48, 0.95]} />
            <meshStandardMaterial color={i === 0 ? "#6b4f2a" : color} flatShading />
          </mesh>
        ))
      ) : style === "service_app" ? (
        <mesh position={[0, height / 2, 0]} castShadow>
          <boxGeometry args={[1.1, height, 0.7]} />
          <meshStandardMaterial color={color} metalness={0.5} roughness={0.3} />
        </mesh>
      ) : (
        <mesh position={[0, height / 2, 0]} castShadow>
          <cylinderGeometry args={[0.55, 0.7, height, 24]} />
          <meshStandardMaterial color={color} roughness={0.35} />
        </mesh>
      )}
      {alert && (
        <mesh ref={glow} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
          <ringGeometry args={[0.9, 1.25, 40]} />
          <meshBasicMaterial color={alert === "decision" ? "#35a37b" : "#e5484d"} transparent />
        </mesh>
      )}
      <Label text={node.label} sub={`${Math.round(health)}%`} color={color} position={[0, height + 0.75, 0]} />
    </group>
  );
}

function Flow({ from, to, load, color }) {
  const count = Math.min(8, Math.max(0, Math.round(load)));
  const refs = useRef([]);
  useFrame(({ clock }) => {
    refs.current.forEach((m, i) => {
      if (!m) return;
      const t = (clock.elapsedTime * 0.35 + i / Math.max(1, count)) % 1;
      m.position.set(from[0] + (to[0] - from[0]) * t, 0.35 + Math.sin(t * Math.PI) * 0.6, from[2] + (to[2] - from[2]) * t);
    });
  });
  return (
    <>
      <Line points={[[from[0], 0.05, from[2]], [to[0], 0.05, to[2]]]} color="#9aa3bd" lineWidth={1.4} />
      {Array.from({ length: count }).map((_, i) => (
        <mesh key={i} ref={(m) => (refs.current[i] = m)}>
          <sphereGeometry args={[0.12, 10, 10]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} />
        </mesh>
      ))}
    </>
  );
}

export function World3D({ run, height = 460, onSelect, playing }) {
  const style = run.environment_style || "workflow";
  const pos = useMemo(() => layered(run.nodes, run.edges), [run.nodes, run.edges]);
  // Fit the camera to the layout so small and large worlds both fill the view.
  const span = Math.max(6, ...Object.values(pos).map((p) => Math.max(Math.abs(p[0]), Math.abs(p[2]))));
  const last = run.history?.at(-1) || {};
  const recent = (run.events || []).filter((e) => e.tick >= run.tick - 3);
  const alerts = {};
  recent.forEach((e) => {
    if (["incident", "cascade", "domain_event", "degradation"].includes(e.kind)) alerts[e.node] = "incident";
    else if (e.kind === "effect" && !alerts[e.node]) alerts[e.node] = "decision";
  });
  return (
    <div className="world3d" style={{ height }}>
      <Canvas shadows camera={{ position: [0, span * 0.8 + 2, span * 1.05 + 3], fov: 45 }} dpr={[1, 1.75]}>
        <color attach="background" args={[style === "voxel" ? "#9fd3ff" : "#0f1426"]} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[8, 14, 6]} intensity={1.1} castShadow />
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[60, 40]} />
          <meshStandardMaterial color={style === "voxel" ? "#5f9e3c" : "#1a2140"} />
        </mesh>
        {style !== "voxel" && <gridHelper args={[60, 30, "#2c3563", "#222a4d"]} position={[0, 0.01, 0]} />}
        {run.edges.map((e, i) =>
          pos[e.source] && pos[e.target] ? (
            <Flow
              key={i}
              from={pos[e.source]}
              to={pos[e.target]}
              load={((last.processing || {})[e.source] || 0) + ((last.queues || {})[e.source] || 0) / 3}
              color={healthColor((last.health || {})[e.target] ?? 100)}
            />
          ) : null,
        )}
        {run.nodes.map((n) => (
          <Tower
            key={n.id}
            node={n}
            position={pos[n.id]}
            health={(last.health || {})[n.id] ?? n.health ?? 100}
            capacity={n.capacity}
            style={style}
            alert={alerts[n.id]}
            onSelect={onSelect}
          />
        ))}
        <OrbitControls enablePan maxPolarAngle={Math.PI / 2.2} autoRotate={!!playing} autoRotateSpeed={0.4} />
      </Canvas>
      <div className="world3d-legend">
        <span><i className="dot green" /> healthy</span>
        <span><i className="dot amber" /> degraded</span>
        <span><i className="dot red" /> critical</span>
        <span>moving spheres = work items in flight · rings = incidents / decisions · drag to orbit</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ deck.gl population */
const STATE_COLORS = {
  S: [120, 170, 230], E: [226, 163, 54], I: [229, 72, 77], H: [150, 40, 160], R: [53, 163, 123],
  flying: [53, 163, 123], charging: [226, 163, 54], landed: [229, 72, 77],
  account: [120, 150, 200], mule: [229, 72, 77],
};

export function PopulationDeck({ data, height = 360 }) {
  const points = data?.snapshot || [];
  const byId = useMemo(() => Object.fromEntries(points.filter((p) => p.id).map((p) => [p.id, p])), [points]);
  const edges = (data?.edges || []).filter((e) => byId[e.source] && byId[e.target]);
  const layers = [
    new LineLayer({
      id: "links",
      data: edges,
      getSourcePosition: (e) => [byId[e.source].x, byId[e.source].y],
      getTargetPosition: (e) => [byId[e.target].x, byId[e.target].y],
      getColor: [229, 72, 77, 90],
      getWidth: 1,
    }),
    new ScatterplotLayer({
      id: "agents",
      data: points,
      getPosition: (p) => [p.x, p.y],
      getRadius: data?.kind === "drones" ? 1.6 : 0.8,
      radiusUnits: "common",
      getFillColor: (p) => STATE_COLORS[p.state] || [140, 140, 160],
      pickable: true,
    }),
  ];
  return (
    <div className="deck-host" style={{ height }}>
      <DeckGL
        views={new OrthographicView({ flipY: true })}
        initialViewState={{ target: [50, 50, 0], zoom: 1.9, minZoom: 0, maxZoom: 6 }}
        controller
        layers={layers}
        getTooltip={({ object }) => object && (object.id || object.state) ? `${object.id || ""} ${object.state}${object.battery != null ? ` · ${object.battery}%` : ""}` : null}
      />
    </div>
  );
}
