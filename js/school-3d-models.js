// Procedural, volumetric garment studies for the Velora School design studio.
// These are concept meshes, not production patterns or simulated cloth.

export function buildGarment(THREE, options = {}) {
  const silhouette = ["dress", "jacket", "set"].includes(options.silhouette) ? options.silhouette : "dress";
  const color = /^#[0-9a-f]{6}$/i.test(options.color || "") ? options.color : "#604032";
  const texture = ["plain", "rib", "woven"].includes(options.texture) ? options.texture : "plain";
  const length = THREE.MathUtils.clamp(Number(options.length) || 1, .8, 1.2);
  const fit = THREE.MathUtils.clamp(Number(options.fit) || 1, .85, 1.15);
  const group = new THREE.Group();
  group.name = `Velora ${silhouette === "dress" ? "Wrap Dress" : silhouette === "jacket" ? "Tailored Jacket" : "Wide-Leg Set"}`;
  group.userData = { silhouette, color, texture, length, fit, conceptModel: true, frontAxis: "+Z" };

  const fabric = new THREE.MeshPhysicalMaterial({
    name: "Velora fabric", color, side: THREE.DoubleSide,
    roughness: texture === "plain" ? .72 : .92, metalness: 0,
    sheen: .22, sheenRoughness: .86, sheenColor: new THREE.Color(color).multiplyScalar(1.18),
  });
  const facing = fabric.clone();
  facing.name = "Velora folded facing";
  facing.color.multiplyScalar(.88);
  const thread = new THREE.MeshStandardMaterial({ name: "Velora tonal stitching", color: new THREE.Color(color).multiplyScalar(.72), roughness: .96 });
  const gold = new THREE.MeshStandardMaterial({ name: "Velora brushed gold hardware", color: "#bd9a62", roughness: .36, metalness: .78 });

  if (texture !== "plain" && typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 128;
    const context = canvas.getContext("2d");
    if (context) {
      context.fillStyle = "#929292";
      context.fillRect(0, 0, 128, 128);
      if (texture === "rib") {
        for (let x = 0; x < 128; x += 8) {
          context.fillStyle = "#b9b9b9"; context.fillRect(x, 0, 2, 128);
          context.fillStyle = "#777777"; context.fillRect(x + 3, 0, 2, 128);
        }
      } else {
        for (let i = 0; i < 128; i += 4) {
          context.fillStyle = i % 8 ? "#a9a9a9" : "#777777";
          context.fillRect(i, 0, 1, 128); context.fillRect(0, i, 128, 1);
        }
      }
      const map = new THREE.CanvasTexture(canvas);
      map.name = `Velora ${texture} fabric height map`;
      map.wrapS = map.wrapT = THREE.RepeatWrapping;
      map.repeat.set(texture === "rib" ? 5 : 7, 7);
      fabric.bumpMap = map; fabric.bumpScale = texture === "rib" ? .011 : .006;
      facing.bumpMap = map; facing.bumpScale = fabric.bumpScale;
    }
  }

  function mesh(geometry, material, name) {
    const object = new THREE.Mesh(geometry, material);
    object.name = name;
    object.castShadow = true;
    object.receiveShadow = true;
    group.add(object);
    return object;
  }

  function stitch(points, name, radius = .0045, material = thread) {
    if (points.length < 2) return;
    const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)));
    return mesh(new THREE.TubeGeometry(curve, Math.max(16, points.length * 3), radius, 5, false), material, name);
  }

  // A swept elliptical fabric shell: the radii change independently through the
  // waist, hips and shoulders, giving a real front, back and side silhouette.
  function shell(profile, name, { folds = 0, centerX = 0, material = fabric, phase = 0, neckline = 0 } = {}) {
    // Monotone cubic lofts retain the authored silhouette without hard horizontal
    // bands or overshooting the waist. Detail panels sample this same surface.
    const authored = profile;
    function radiusAt(index, component, t) {
      const left = authored[index], right = authored[index + 1];
      const a = left[component] ?? (component === 3 ? 1 : centerX);
      const b = right[component] ?? (component === 3 ? 1 : centerX);
      const span = right[0] - left[0], slope = (b - a) / span;
      const tangent = (row) => {
        if (row === 0 || row === authored.length - 1) return slope;
        const previous = authored[row - 1], current = authored[row], next = authored[row + 1];
        const value = (point) => point[component] ?? (component === 3 ? 1 : centerX);
        const before = (value(current) - value(previous)) / (current[0] - previous[0]);
        const after = (value(next) - value(current)) / (next[0] - current[0]);
        return before * after <= 0 ? 0 : 2 * before * after / (before + after);
      };
      return (2 * t ** 3 - 3 * t ** 2 + 1) * a + (t ** 3 - 2 * t ** 2 + t) * span * tangent(index)
        + (-2 * t ** 3 + 3 * t ** 2) * b + (t ** 3 - t ** 2) * span * tangent(index + 1);
    }
    profile = [];
    for (let row = 0; row < authored.length - 1; row++) {
      const steps = Math.max(1, Math.ceil((authored[row + 1][0] - authored[row][0]) / .045));
      for (let step = 0; step < steps; step++) {
        const t = step / steps;
        profile.push([THREE.MathUtils.lerp(authored[row][0], authored[row + 1][0], t),
          ...[1, 2, 3, 4].map((component) => radiusAt(row, component, t))]);
      }
    }
    profile.push(authored.at(-1));
    const radialSegments = 80;
    const vertices = [], uvs = [], indices = [];
    const minY = profile[0][0], maxY = profile.at(-1)[0];
    for (let row = 0; row < profile.length; row++) {
      const [y, rx, rz, foldWeight = 1, cx = centerX] = profile[row];
      for (let side = 0; side <= radialSegments; side++) {
        const theta = side / radialSegments * Math.PI * 2;
        const wave = folds * foldWeight * (Math.cos(theta * 12 + phase) + .3 * Math.sin(theta * 19 + y * 1.8));
        const rib = texture === "rib" ? .0018 * Math.cos(theta * 64) : 0;
        const necklineDrop = Math.sin(theta) > 0 ? neckline * ((y - minY) / (maxY - minY)) * (1 - Math.abs(Math.cos(theta))) : 0;
        vertices.push(cx + Math.cos(theta) * (rx + wave + rib), y - necklineDrop, Math.sin(theta) * (rz + wave * .55 + rib));
        uvs.push(side / radialSegments, (y - minY) / (maxY - minY || 1));
        if (row < profile.length - 1 && side < radialSegments) {
          const a = row * (radialSegments + 1) + side;
          const b = a + radialSegments + 1;
          indices.push(a, b, a + 1, b, b + 1, a + 1);
        }
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    mesh(geometry, material, name);
    return profile;
  }

  function rim(y, rx, rz, name, cx = 0, radius = .006) {
    const points = [];
    for (let i = 0; i <= 80; i++) {
      const t = i / 80 * Math.PI * 2;
      points.push([cx + Math.cos(t) * rx, y, Math.sin(t) * rz]);
    }
    stitch(points, name, radius);
  }

  function sampleProfile(profile, y) {
    for (let i = 0; i < profile.length - 1; i++) {
      if (y >= profile[i][0] && y <= profile[i + 1][0]) {
        const t = (y - profile[i][0]) / (profile[i + 1][0] - profile[i][0]);
        return [THREE.MathUtils.lerp(profile[i][1], profile[i + 1][1], t), THREE.MathUtils.lerp(profile[i][2], profile[i + 1][2], t)];
      }
    }
    const edge = y < profile[0][0] ? profile[0] : profile.at(-1);
    return [edge[1], edge[2]];
  }

  function frontZ(profile, x, y, lift = .013) {
    const [rx, rz] = sampleProfile(profile, y);
    return Math.sqrt(Math.max(.02, 1 - (x / rx) ** 2)) * rz + lift;
  }

  // Small fabric panels follow the curved front of the garment rather than
  // becoming flat billboard details when the wearer rotates the model.
  function panel(points, profile, name, material = facing, lift = .018) {
    const outline = points.map(([x, y]) => new THREE.Vector2(x, y));
    const triangles = THREE.ShapeUtils.triangulateShape(outline, []);
    const positions = [], uvs = [];
    // Project a finely tessellated panel onto the elliptical torso. Merely
    // lifting the polygon's corner vertices leaves its flat interior triangles
    // passing through the curved fabric surface, especially on long lapels.
    const divisions = 14;
    const pointAt = (a, b, c, u, v) => [
      a[0] + (b[0] - a[0]) * u + (c[0] - a[0]) * v,
      a[1] + (b[1] - a[1]) * u + (c[1] - a[1]) * v,
    ];
    const addTriangle = (a, b, c) => {
      for (const [x, y] of [a, b, c]) {
        positions.push(x, y, frontZ(profile, x, y, lift));
        uvs.push(x + .5, y);
      }
    };
    for (const triangle of triangles) {
      const [a, b, c] = triangle.map(index => points[index]);
      for (let row = 0; row < divisions; row++) {
        for (let column = 0; column < divisions - row; column++) {
          const p00 = pointAt(a, b, c, row / divisions, column / divisions);
          const p10 = pointAt(a, b, c, (row + 1) / divisions, column / divisions);
          const p01 = pointAt(a, b, c, row / divisions, (column + 1) / divisions);
          addTriangle(p00, p10, p01);
          if (column < divisions - row - 1) {
            const p11 = pointAt(a, b, c, (row + 1) / divisions, (column + 1) / divisions);
            addTriangle(p10, p11, p01);
          }
        }
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.computeVertexNormals();
    mesh(geometry, material, name);
  }

  function sleeve(sign, lowerY = 1.72, cuffRadius = .105) {
    // Start the sleeve cap inside the shoulder, then ease it into its full
    // circumference. This conceals the tube opening and joins it to the body.
    const start = new THREE.Vector3(sign * .43, 2.84, 0);
    const end = new THREE.Vector3(sign * .99, lowerY, .035);
    const axis = end.clone().sub(start).normalize();
    const depth = new THREE.Vector3(0, 0, 1);
    const across = new THREE.Vector3().crossVectors(depth, axis).normalize();
    const vertices = [], uvs = [], indices = [];
    const rows = 18, sides = 40;
    for (let row = 0; row <= rows; row++) {
      const t = row / rows;
      const center = start.clone().lerp(end, t);
      // A soft elbow and a small sleeve-head ease are actual mesh shaping.
      center.z += Math.sin(t * Math.PI) * .035;
      const sleeveEase = THREE.MathUtils.smoothstep(t, 0, .19);
      const radius = (THREE.MathUtils.lerp(.215 * fit, cuffRadius * fit, t) + Math.sin(t * Math.PI) * .012) * THREE.MathUtils.lerp(.12, 1, sleeveEase);
      for (let side = 0; side <= sides; side++) {
        const theta = side / sides * Math.PI * 2;
        const ripple = .006 * Math.sin(theta * 7 + t * 16) * Math.sin(t * Math.PI);
        const point = center.clone().addScaledVector(across, Math.cos(theta) * (radius + ripple)).addScaledVector(depth, Math.sin(theta) * radius * .92);
        vertices.push(point.x, point.y, point.z); uvs.push(side / sides, t);
        if (row < rows && side < sides) {
          const a = row * (sides + 1) + side, b = a + sides + 1;
          indices.push(a, a + 1, b, b, a + 1, b + 1);
        }
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices); geometry.computeVertexNormals();
    mesh(geometry, fabric, `${sign < 0 ? "Left" : "Right"} shaped sleeve`);
    const cuffPoints = [];
    for (let side = 0; side <= sides; side++) {
      const theta = side / sides * Math.PI * 2;
      const point = end.clone().addScaledVector(across, Math.cos(theta) * cuffRadius * fit).addScaledVector(depth, Math.sin(theta) * cuffRadius * fit * .92);
      cuffPoints.push([point.x, point.y, point.z]);
    }
    stitch(cuffPoints, `${sign < 0 ? "Left" : "Right"} cuff seam`, .0055);
  }

  function button(x, y, z, name) {
    const object = mesh(new THREE.SphereGeometry(.028, 16, 10), gold, name);
    object.scale.z = .4;
    object.position.set(x, y, z);
  }

  function buckle(x, y, z) {
    const bar = (w, h, px, py) => {
      const object = mesh(new THREE.BoxGeometry(w, h, .018), gold, "Brushed gold belt buckle");
      object.position.set(x + px, y + py, z);
    };
    bar(.145, .012, 0, -.05); bar(.145, .012, 0, .05);
    bar(.012, .10, -.072, 0); bar(.012, .10, .072, 0);
    bar(.07, .008, .025, 0);
  }

  if (silhouette === "dress") {
    const waist = 1.86;
    const hem = waist - 1.68 * length;
    const skirt = shell([
      [hem, .88 * fit, .42, 1], [hem + .12, .85 * fit, .41, 1],
      [waist - 1.2 * length, .73 * fit, .36, .85], [waist - .8 * length, .62 * fit, .32, .55],
      [waist - .35 * length, .49 * fit, .28, .2], [waist, .405 * fit, .235, .02],
    ], "Draped wrap skirt", { folds: .024 });
    const bodice = shell([
      [waist, .405 * fit, .235], [2.03, .425 * fit, .25], [2.30, .52 * fit, .29],
      [2.55, .575 * fit, .285], [2.75, .60 * fit, .255], [2.86, .58 * fit, .23],
      [2.97, .35, .195], [3.02, .235, .17],
    ], "Shaped V-neck wrap bodice", { folds: .004, neckline: .54 });
    sleeve(-1); sleeve(1);
    const neckline = [];
    for (let i = 0; i <= 80; i++) {
      const theta = i / 80 * Math.PI * 2;
      const drop = Math.sin(theta) > 0 ? .54 * (1 - Math.abs(Math.cos(theta))) : 0;
      neckline.push([Math.cos(theta) * .235, 3.02 - drop, Math.sin(theta) * .17]);
    }
    stitch(neckline, "Folded V-neckline edge", .013, facing);
    rim(hem + .018, .88 * fit, .42, "Skirt hem stitching");
    const wrappedFrontZ = (x, y) => {
      const samples = bodice.map(([originalY, rx, rz]) => {
        const ratio = Math.min(.999, Math.abs(x / rx));
        return [originalY - .54 * (originalY - waist) / (3.02 - waist) * (1 - ratio), Math.sqrt(1 - ratio * ratio) * rz];
      });
      for (let i = 0; i < samples.length - 1; i++) {
        if (y >= samples[i][0] && y <= samples[i + 1][0]) {
          const t = (y - samples[i][0]) / (samples[i + 1][0] - samples[i][0]);
          return THREE.MathUtils.lerp(samples[i][1], samples[i + 1][1], t) + .014;
        }
      }
      return samples.at(-1)[1] + .014;
    };
    const diagonal = [];
    for (let i = 0; i <= 28; i++) {
      const t = i / 28, y = THREE.MathUtils.lerp(2.48, waist, t), x = THREE.MathUtils.lerp(0, .30 * fit, t);
      diagonal.push([x, y, wrappedFrontZ(x, y)]);
    }
    stitch(diagonal, "Diagonal wrap neckline", .009, facing);
    const wrapEdge = [];
    for (let i = 0; i <= 36; i++) {
      const t = i / 36, y = THREE.MathUtils.lerp(waist - .02, hem + .03, t), x = (.28 + .10 * t) * fit;
      wrapEdge.push([x, y, frontZ(skirt, x, y, .025)]);
    }
    stitch(wrapEdge, "Overlapping wrap skirt edge", .008, facing);
    shell([[1.81, .411 * fit, .245], [1.89, .411 * fit, .245]], "Fabric waist belt", { material: facing });
    buckle(.10, 1.85, .261);
    const tie = [[.20, 1.83, .27], [.35, 1.72, .29], [.39, 1.48, .31], [.36, 1.27, .34]];
    stitch(tie, "Soft hanging belt tie", .025, facing);
  } else if (silhouette === "jacket") {
    const hem = 2.84 - 1.48 * length;
    const body = shell([
      [hem, .52 * fit, .27], [hem + .12, .515 * fit, .275], [1.95, .455 * fit, .255],
      [2.20, .50 * fit, .29], [2.52, .59 * fit, .30], [2.78, .635 * fit, .265],
      [2.87, .60 * fit, .235], [2.99, .35, .20], [3.05, .235, .18],
    ].sort((a, b) => a[0] - b[0]), "Tailored jacket body");
    sleeve(-1, 1.59); sleeve(1, 1.59);
    rim(3.05, .235, .18, "Back collar edge", 0, .009);
    rim(hem + .012, .52 * fit, .27, "Jacket hem stitching");
    panel([[-.20, 3.00], [-.38, 2.76], [-.26, 2.59], [-.33, 2.50], [0, 2.14], [-.08, 2.69]], body, "Left notched lapel");
    panel([[.20, 3.00], [.38, 2.76], [.26, 2.59], [.33, 2.50], [0, 2.14], [.08, 2.69]], body, "Right notched lapel");
    stitch([[0, 2.15, .31], [0, 1.95, .278], [0, hem + .035, .287]], "Center front jacket opening", .008, facing);
    for (const sign of [-1, 1]) {
      const x = .32 * sign * fit, y = Math.max(hem + .26, 1.63);
      panel([[x - .13, y + .09], [x + .13, y + .09], [x + .12, y - .015], [x - .12, y - .015]], body, `${sign < 0 ? "Left" : "Right"} pocket flap`, facing, .027);
      button(sign * .135, 1.96, .285, "Gold jacket waist button");
      button(sign * .135, 1.70, frontZ(body, .135, 1.70, .033), "Gold jacket lower button");
    }
    const shoulderSeam = sign => stitch([[sign * .24, 2.98, .03], [sign * .43, 2.91, .035], [sign * .60, 2.79, .04]], "Shaped shoulder seam", .005);
    shoulderSeam(-1); shoulderSeam(1);
  } else {
    shell([
      [1.88, .46 * fit, .255], [2.12, .475 * fit, .27], [2.45, .55 * fit, .28],
      [2.72, .60 * fit, .255], [2.84, .575 * fit, .23], [2.97, .33, .19], [3.015, .225, .165],
    ], "Relaxed matching knit top", { folds: .005 });
    sleeve(-1, 1.81, .105); sleeve(1, 1.81, .105);
    rim(3.015, .225, .165, "Soft crew neckline", 0, .010);
    rim(1.89, .46 * fit, .255, "Top ribbed hem", 0, .010);
    shell([[1.54, .49 * fit, .28], [1.68, .51 * fit, .29], [1.82, .465 * fit, .265]], "Trouser hips and rise", { folds: .004 });
    const hem = 1.69 - 1.53 * length;
    for (const sign of [-1, 1]) {
      const center = sign * .275 * fit;
      shell([
        [hem, .285 * fit, .27, .7], [hem + .12, .28 * fit, .27, .8],
        [.67, .26 * fit, .25, .45], [1.10, .245 * fit, .25, .2],
        [1.40, .255 * fit, .27, .15], [1.66, .275 * fit, .28, .02],
      ].sort((a, b) => a[0] - b[0]), `${sign < 0 ? "Left" : "Right"} wide trouser leg`, { centerX: center, folds: .010, phase: sign });
      rim(hem + .015, .285 * fit, .27, "Trouser hem seam", center);
      stitch([[center, 1.60, .295], [center, 1.15, .265], [center, .69, .265], [center, hem + .03, .285]], "Pressed front trouser crease", .0035);
    }
    shell([[1.755, .471 * fit, .273], [1.825, .471 * fit, .273]], "Trouser waistband", { material: facing });
    buckle(0, 1.79, .292);
  }

  // Different hem lengths stay grounded at the same studio floor.
  const bounds = new THREE.Box3().setFromObject(group);
  group.position.y = .075 - bounds.min.y;
  group.updateMatrixWorld(true);
  const groundedBounds = new THREE.Box3().setFromObject(group);
  const dimensions = groundedBounds.getSize(new THREE.Vector3());
  group.userData.dimensions = { width: dimensions.x, height: dimensions.y, depth: dimensions.z };
  return group;
}
