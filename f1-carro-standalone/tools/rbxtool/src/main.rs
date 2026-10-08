use std::collections::HashMap;
use std::fs;
use std::io::{BufReader, BufWriter, Write};
use std::path::Path;

use rbx_dom_weak::types::{Ref, Variant};
use rbx_dom_weak::WeakDom;

fn load(p: &str) -> WeakDom {
    let f = BufReader::new(fs::File::open(p).expect("open"));
    if p.ends_with(".rbxlx") || p.ends_with(".rbxmx") {
        rbx_xml::from_reader(
            f,
            rbx_xml::DecodeOptions::new()
                .property_behavior(rbx_xml::DecodePropertyBehavior::ReadUnknown),
        )
        .expect("xml decode")
    } else {
        rbx_binary::from_reader(f).expect("binary decode")
    }
}

fn save(dom: &WeakDom, refs: &[Ref], p: &str) {
    let f = BufWriter::new(fs::File::create(p).expect("create"));
    if p.ends_with(".rbxlx") || p.ends_with(".rbxmx") {
        rbx_xml::to_writer(
            f,
            dom,
            refs,
            rbx_xml::EncodeOptions::new()
                .property_behavior(rbx_xml::EncodePropertyBehavior::WriteUnknown),
        )
        .expect("xml encode");
    } else {
        rbx_binary::to_writer(f, dom, refs).expect("binary encode");
    }
}

/// Unique-ish path: names joined by '/', duplicate sibling names get a #n suffix.
fn build_paths(dom: &WeakDom) -> HashMap<Ref, String> {
    let mut out = HashMap::new();
    let root = dom.root_ref();
    out.insert(root, String::new());
    let mut stack = vec![root];
    while let Some(r) = stack.pop() {
        let inst = dom.get_by_ref(r).unwrap();
        let base = out[&r].clone();
        let mut seen: HashMap<String, usize> = HashMap::new();
        for &c in inst.children() {
            let ci = dom.get_by_ref(c).unwrap();
            let n = seen.entry(ci.name.clone()).or_insert(0);
            *n += 1;
            let nm = if *n > 1 { format!("{}#{}", ci.name, n) } else { ci.name.clone() };
            let p = if base.is_empty() { nm } else { format!("{}/{}", base, nm) };
            out.insert(c, p);
            stack.push(c);
        }
    }
    out
}

fn fmt_val(v: &Variant, paths: &HashMap<Ref, String>) -> String {
    match v {
        Variant::Ref(r) => {
            if r.is_none() { "nil".into() } else { format!("Ref({})", paths.get(r).cloned().unwrap_or("?".into())) }
        }
        Variant::String(s) => format!("{:?}", if s.len() > 200 { &s[..200] } else { s }),
        Variant::BinaryString(b) => format!("Binary({} bytes)", AsRef::<[u8]>::as_ref(b).len()),
        Variant::SharedString(s) => format!("SharedString({} bytes)", s.data().len()),
        other => {
            let s = format!("{:?}", other);
            if s.len() > 400 { format!("{}...", &s[..400]) } else { s }
        }
    }
}

fn is_script(class: &str) -> bool {
    matches!(class, "Script" | "LocalScript" | "ModuleScript")
}

fn dump(input: &str, outdir: &str) {
    let dom = load(input);
    let paths = build_paths(&dom);
    let out = Path::new(outdir);
    fs::create_dir_all(out.join("src")).unwrap();
    let mut tree = BufWriter::new(fs::File::create(out.join("tree.txt")).unwrap());
    let mut props = BufWriter::new(fs::File::create(out.join("props.txt")).unwrap());
    let mut order: Vec<&Ref> = paths.keys().collect();
    order.sort_by_key(|r| paths[r].clone());
    for r in order {
        if *r == dom.root_ref() { continue; }
        let inst = dom.get_by_ref(*r).unwrap();
        let p = &paths[r];
        let depth = p.matches('/').count();
        writeln!(tree, "{}{} [{}]", "  ".repeat(depth), p, inst.class).unwrap();
        writeln!(props, "== {} [{}]", p, inst.class).unwrap();
        let mut keys: Vec<_> = inst.properties.keys().collect();
        keys.sort();
        for k in keys {
            if k.as_str() == "Source" { continue; }
            writeln!(props, "    {} = {}", k, fmt_val(&inst.properties[k], &paths)).unwrap();
        }
        if is_script(&inst.class) {
            if let Some(Variant::String(src)) = inst.properties.get(&"Source".into()) {
                let ext = match inst.class.as_str() { "Script" => "server.lua", "LocalScript" => "client.lua", _ => "lua" };
                let fp = out.join("src").join(format!("{}.{}", p.replace(':', "_"), ext));
                fs::create_dir_all(fp.parent().unwrap()).unwrap();
                fs::write(fp, src).unwrap();
            }
        }
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    match a[1].as_str() {
        "dump" => dump(&a[2], &a[3]),
        "convert" => {
            let dom = load(&a[2]);
            let refs = dom.root().children().to_vec();
            save(&dom, &refs, &a[3]);
        }
        "addscripts" => addscripts(&a),
        "blob" => blob(&a[2], &a[3], &a[4], &a[5]),
        "chassis" => chassis(&a[2], &a[3], &a[4]),
        "place" => place_into(&a[2], &a[3], &a[4], &a[5]),
        "build" => build(&a[2], &a[3], &a[4], &a[5]),
        "v2" => v2(&a[2], &a[3], &a[4], a.get(5).map(|x| x.as_str())),
        _ => panic!("unknown cmd"),
    }
}

// ---------------------------------------------------------------------------
// build: standalone F1 car (task specific)
// ---------------------------------------------------------------------------
use rbx_dom_weak::types::{Attributes, CFrame, Content, Vector3};
use rbx_dom_weak::InstanceBuilder;

fn child(dom: &WeakDom, parent: Ref, name: &str) -> Option<Ref> {
    dom.get_by_ref(parent)?.children().iter().copied().find(|c| dom.get_by_ref(*c).unwrap().name == name)
}

fn find(dom: &WeakDom, path: &str) -> Ref {
    let mut cur = dom.root_ref();
    for part in path.split('/') {
        cur = child(dom, cur, part).unwrap_or_else(|| panic!("missing {path} at {part}"));
    }
    cur
}

fn destroy_children_except(dom: &mut WeakDom, parent: Ref, keep: &[&str]) {
    let kids = dom.get_by_ref(parent).unwrap().children().to_vec();
    for c in kids {
        let n = dom.get_by_ref(c).unwrap().name.clone();
        if !keep.contains(&n.as_str()) {
            dom.destroy(c);
        }
    }
}

fn destroy_named(dom: &mut WeakDom, parent: Ref, names: &[&str]) {
    let kids = dom.get_by_ref(parent).unwrap().children().to_vec();
    for c in kids {
        let n = dom.get_by_ref(c).unwrap().name.clone();
        if names.contains(&n.as_str()) {
            dom.destroy(c);
        }
    }
}

fn set_prop(dom: &mut WeakDom, r: Ref, k: &str, v: Variant) {
    dom.get_by_ref_mut(r).unwrap().properties.insert(k.into(), v);
}

/// Clone `src` as a new instance named `name` under `parent`, with a new Source.
fn clone_to(dom: &mut WeakDom, src: Ref, parent: Ref, name: &str) -> Ref {
    let c = dom.clone_within(src);
    dom.transfer_within(c, parent);
    let refs: Vec<Ref> = dom.descendants_of(c).map(|i| i.referent()).collect();
    for r in refs {
        dom.get_by_ref_mut(r).unwrap().properties.remove(&"UniqueId".into());
    }
    dom.get_by_ref_mut(c).unwrap().name = name.to_string();
    c
}

fn read_src(p: &str) -> String {
    fs::read_to_string(p).unwrap_or_else(|_| panic!("read {p}"))
}

const BASEPART: &[&str] = &["Part", "MeshPart", "VehicleSeat", "Seat", "UnionOperation", "WedgePart", "CornerWedgePart", "TrussPart", "SpawnLocation", "IntersectOperation", "NegateOperation"];

fn translate_tree(dom: &mut WeakDom, root: Ref, d: Vector3) {
    let refs: Vec<Ref> = dom.descendants_of(root).map(|i| i.referent()).collect();
    for r in refs {
        let inst = dom.get_by_ref_mut(r).unwrap();
        let class = inst.class.to_string();
        if BASEPART.contains(&class.as_str()) {
            if let Some(Variant::CFrame(cf)) = inst.properties.get_mut(&"CFrame".into()) {
                cf.position = Vector3::new(cf.position.x + d.x, cf.position.y + d.y, cf.position.z + d.z);
            }
        }
        if class == "Model" {
            if let Some(Variant::OptionalCFrame(Some(cf))) = inst.properties.get_mut(&"WorldPivotData".into()) {
                cf.position = Vector3::new(cf.position.x + d.x, cf.position.y + d.y, cf.position.z + d.z);
            }
            if let Some(Variant::CFrame(cf)) = inst.properties.get_mut(&"ModelMeshCFrame".into()) {
                cf.position = Vector3::new(cf.position.x + d.x, cf.position.y + d.y, cf.position.z + d.z);
            }
        }
    }
}

fn cframe_of(dom: &WeakDom, r: Ref) -> CFrame {
    match dom.get_by_ref(r).unwrap().properties.get(&"CFrame".into()) {
        Some(Variant::CFrame(c)) => *c,
        _ => panic!("no cframe"),
    }
}
fn size_of(dom: &WeakDom, r: Ref) -> Vector3 {
    match dom.get_by_ref(r).unwrap().properties.get(&"Size".into()) {
        Some(Variant::Vector3(v)) => *v,
        _ => panic!("no size"),
    }
}

fn build(input: &str, srcdir: &str, out_place: &str, out_pkg: &str) {
    let mut dom = load(input);
    let s = |f: &str| read_src(&format!("{srcdir}/{f}"));

    // ---------------- templates we need before pruning ----------------
    let tpl_server = find(&dom, "ServerScriptService/NoColide");           // Script (enabled)
    let tpl_local = find(&dom, "ServerStorage/ScriptCarro");               // LocalScript (enabled)
    let tpl_module = find(&dom, "ReplicatedStorage/Skins");                // ModuleScript
    let tpl_track = {
        // a collidable asphalt piece of workspace.Pista (Material 1376, friction 0.5, weight 0)
        let pista = find(&dom, "Workspace/Pista");
        dom.get_by_ref(pista).unwrap().children().iter().copied().find(|c| {
            let i = dom.get_by_ref(*c).unwrap();
            i.name == "Track" && i.class == "Part"
                && matches!(i.properties.get(&"CanCollide".into()), Some(Variant::Bool(true)))
                && matches!(i.properties.get(&"Material".into()), Some(Variant::Enum(e)) if e.to_u32() == 1376)
        }).expect("track template")
    };
    let tpl_spawn = find(&dom, "Workspace/SpawnLocation");

    let ws = find(&dom, "Workspace");
    let rs = find(&dom, "ReplicatedStorage");
    let sss = find(&dom, "ServerScriptService");
    let ss = find(&dom, "ServerStorage");
    let sg = find(&dom, "StarterGui");
    let sp = find(&dom, "StarterPlayer");
    let spc = find(&dom, "StarterPlayer/StarterCharacterScripts");
    let sps = find(&dom, "StarterPlayer/StarterPlayerScripts");

    // ---------------- the car ----------------
    let car = find(&dom, "ServerStorage/Carros/Carro");
    let chassi = child(&dom, car, "Chassi").unwrap();
    destroy_named(&mut dom, car, &["AreaPit"]);
    destroy_named(&mut dom, chassi, &["TimerUP"]);
    let script_car = child(&dom, chassi, "ScriptCar").unwrap();
    set_prop(&mut dom, script_car, "Source", Variant::String(s("ScriptCar.server.lua")));

    // keep only damage/repair attributes on the chassis
    {
        let inst = dom.get_by_ref_mut(chassi).unwrap();
        if let Some(Variant::Attributes(a)) = inst.properties.get_mut(&"Attributes".into()) {
            let keys: Vec<String> = a.iter().map(|(k, _)| k.clone()).collect();
            println!("chassi attributes: {:?}", keys);
            for k in keys {
                if !["AsaBroken", "EixoFdBroken", "EixoFeBroken", "Inpit"].contains(&k.as_str()) {
                    a.remove(k.as_str());
                }
            }
        }
    }

    // Config (spawn tuning that ServerScriptService.Principal applied with the garage defaults)
    let cfg_attrs = Attributes::new()
        .with("AplicarTuning", true)
        .with("MolalturaF", 1.5f64)
        .with("MolalturaT", 1.5f64)
        .with("RigidezF", 25000.0f64)
        .with("RigidezT", 25000.0f64)
        .with("CamberF", 90.0f64)
        .with("CamberT", 90.0f64)
        .with("Sensibilidade", 1.5f64)
        .with("TC", 1.0f64);
    dom.insert(car, InstanceBuilder::new("Configuration").with_name("Config").with_property("Attributes", cfg_attrs));

    // default skin = first free skin of the garage (Sauter ST25); purely visual
    let tex = |dom: &mut WeakDom, path: &str, id: &str| {
        let r = find(dom, &format!("ServerStorage/Carros/Carro/{path}"));
        set_prop(dom, r, "TextureContent", Variant::Content(Content::from_uri(id)));
    };
    tex(&mut dom, "Corpo", "rbxassetid://114691956210167");
    tex(&mut dom, "Corpo/AsaFrontal", "rbxassetid://73335050173922");
    tex(&mut dom, "Corpo/AsaCopia", "rbxassetid://73335050173922");
    tex(&mut dom, "Corpo/aerofolio", "rbxassetid://73732279418203");
    for w in ["Chassi/EixoFE/RodaFE", "Chassi/EixoFD/RodaFD", "Chassi/EixoT/RodaTD", "Chassi/EixoT/RodaTE"] {
        tex(&mut dom, &format!("{w}/Pneu/Aro"), "rbxassetid://129311585774518");
    }

    // move the car next to the world origin, wheels resting on y = 0
    let wheels = ["Chassi/EixoFE/RodaFE", "Chassi/EixoFD/RodaFD", "Chassi/EixoT/RodaTD", "Chassi/EixoT/RodaTE"];
    let mut min_y = f32::MAX;
    for w in wheels {
        let r = find(&dom, &format!("ServerStorage/Carros/Carro/{w}"));
        let (cf, sz) = (cframe_of(&dom, r), size_of(&dom, r));
        min_y = min_y.min(cf.position.y - sz.y / 2.0);
    }
    let pivot = match dom.get_by_ref(car).unwrap().properties.get(&"WorldPivotData".into()) {
        Some(Variant::OptionalCFrame(Some(c))) => *c,
        _ => panic!(),
    };
    // the car is NOT moved (keeps its exact saved coordinates); the ground goes under it
    let ground_top = min_y - 0.05;
    println!("wheel bottom y={min_y}, ground top y={ground_top}, pivot {:?}", pivot.position);

    // ---------------- ReplicatedStorage ----------------
    let ev = child(&dom, rs, "EventsCar").unwrap();
    destroy_children_except(&mut dom, ev, &["Join", "Leave", "DRS"]);
    let mc = child(&dom, rs, "ModuleCar").unwrap();
    destroy_children_except(&mut dom, mc, &["ModuleCar", "ModuleSom"]);
    let m1 = child(&dom, mc, "ModuleCar").unwrap();
    set_prop(&mut dom, m1, "Source", Variant::String(s("ModuleCar.lua")));
    let m2 = child(&dom, mc, "ModuleSom").unwrap();
    set_prop(&mut dom, m2, "Source", Variant::String(s("ModuleSom.lua")));

    // ---------------- scripts ----------------
    let srv = clone_to(&mut dom, tpl_server, sss, "CarroStandalone");
    set_prop(&mut dom, srv, "Source", Variant::String(s("CarroStandalone.server.lua")));
    let cli = clone_to(&mut dom, tpl_local, spc, "ScriptCarro");
    set_prop(&mut dom, cli, "Source", Variant::String(s("ScriptCarro.client.lua")));
    let readme = clone_to(&mut dom, tpl_module, ws, "LEIA-ME");
    set_prop(&mut dom, readme, "Source", Variant::String(s("LEIA-ME.lua")));

    // ---------------- GUI: keep driving HUD, drop race HUD ----------------
    for g in ["GUIcar", "GUIMobileCar"] {
        let iface = find(&dom, &format!("StarterGui/{g}/Interface"));
        destroy_named(&mut dom, iface, &["Pos", "Lap", "List", "Time", "Radio", "Flags"]);
    }

    // ---------------- test ground ----------------
    let chao = clone_to(&mut dom, tpl_track, ws, "PistaTeste");
    set_prop(&mut dom, chao, "Size", Variant::Vector3(Vector3::new(2048.0, 4.0, 2048.0)));
    set_prop(&mut dom, chao, "CFrame", Variant::CFrame(CFrame::new(Vector3::new(pivot.position.x, ground_top - 2.0, pivot.position.z), rbx_dom_weak::types::Matrix3::identity())));
    set_prop(&mut dom, chao, "Anchored", Variant::Bool(true));
    let spawn = clone_to(&mut dom, tpl_spawn, ws, "SpawnLocation");
    let mut spawn_cf = cframe_of(&dom, spawn);
    let spawn_sz = size_of(&dom, spawn);
    spawn_cf.position = Vector3::new(pivot.position.x + 30.0, ground_top + spawn_sz.y / 2.0, pivot.position.z + 30.0);
    set_prop(&mut dom, spawn, "CFrame", Variant::CFrame(spawn_cf));

    // ---------------- prune everything else ----------------
    // Workspace: keep only what we created (by reference: the old map also has a "Carro" and a "SpawnLocation")
    let keep_refs = [find(&dom, "Workspace/Camera"), find(&dom, "Workspace/Terrain"), chao, spawn, readme];
    let kids = dom.get_by_ref(ws).unwrap().children().to_vec();
    for c in kids {
        if !keep_refs.contains(&c) {
            dom.destroy(c);
        }
    }
    // car goes to Workspace before ServerStorage is cleared
    dom.transfer_within(car, ws);
    destroy_children_except(&mut dom, rs, &["EventsCar", "ModuleCar"]);
    destroy_children_except(&mut dom, sss, &["CarroStandalone"]);
    destroy_children_except(&mut dom, ss, &[]);
    destroy_children_except(&mut dom, sg, &["GUIcar", "GUIMobileCar"]);
    destroy_children_except(&mut dom, sps, &[]);
    destroy_children_except(&mut dom, spc, &["ScriptCarro"]);
    let _ = sp;

    // ---------------- write the test place ----------------
    let top = dom.root().children().to_vec();
    save(&dom, &top, out_place);

    // ---------------- write the package model ----------------
    let mut pkg = WeakDom::new(InstanceBuilder::new("DataModel"));
    let proot = pkg.insert(pkg.root_ref(), InstanceBuilder::new("Folder").with_name("F1_Carro_Standalone"));
    let mk = |pkg: &mut WeakDom, parent: Ref, name: &str| pkg.insert(parent, InstanceBuilder::new("Folder").with_name(name));
    let f_ws = mk(&mut pkg, proot, "Workspace");
    let f_rs = mk(&mut pkg, proot, "ReplicatedStorage");
    let f_sss = mk(&mut pkg, proot, "ServerScriptService");
    let f_sg = mk(&mut pkg, proot, "StarterGui");
    let f_sp = mk(&mut pkg, proot, "StarterPlayer");
    let f_spc = mk(&mut pkg, f_sp, "StarterCharacterScripts");
    let place = |p: &str| find(&dom, p);
    let items: Vec<(Ref, Ref)> = vec![
        (place("Workspace/LEIA-ME"), proot),
        (place("Workspace/Carro"), f_ws),
        (place("ReplicatedStorage/EventsCar"), f_rs),
        (place("ReplicatedStorage/ModuleCar"), f_rs),
        (place("ServerScriptService/CarroStandalone"), f_sss),
        (place("StarterGui/GUIcar"), f_sg),
        (place("StarterGui/GUIMobileCar"), f_sg),
        (place("StarterPlayer/StarterCharacterScripts/ScriptCarro"), f_spc),
    ];
    let srcs: Vec<Ref> = items.iter().map(|(s, _)| *s).collect();
    let clones = dom.clone_multiple_into_external(&srcs, &mut pkg);
    for (c, (_, dest)) in clones.iter().zip(items.iter()) {
        pkg.transfer_within(*c, *dest);
    }
    save(&pkg, &[proot], out_pkg);
}

// ---------------------------------------------------------------------------
// place: put the standalone package into another map (Spa)
// ---------------------------------------------------------------------------
use rbx_dom_weak::types::Matrix3;

fn mrow(m: &Matrix3, i: usize) -> [f32; 3] {
    let r = [m.x, m.y, m.z][i];
    [r.x, r.y, r.z]
}
fn mat_mul(a: &Matrix3, b: &Matrix3) -> Matrix3 {
    // rows convention: (a*b)[i][j] = sum_k a[i][k] * b[k][j]
    let ar: Vec<[f32; 3]> = (0..3).map(|i| mrow(a, i)).collect();
    let br: Vec<[f32; 3]> = (0..3).map(|i| mrow(b, i)).collect();
    let mut o = [[0f32; 3]; 3];
    for i in 0..3 { for j in 0..3 { o[i][j] = (0..3).map(|k| ar[i][k] * br[k][j]).sum(); } }
    Matrix3::new(Vector3::new(o[0][0], o[0][1], o[0][2]), Vector3::new(o[1][0], o[1][1], o[1][2]), Vector3::new(o[2][0], o[2][1], o[2][2]))
}
fn mat_vec(a: &Matrix3, v: Vector3) -> Vector3 {
    let r = |i| { let r = mrow(a, i); r[0] * v.x + r[1] * v.y + r[2] * v.z };
    Vector3::new(r(0), r(1), r(2))
}
fn cf_mul(a: &CFrame, b: &CFrame) -> CFrame {
    let p = mat_vec(&a.orientation, b.position);
    CFrame::new(Vector3::new(p.x + a.position.x, p.y + a.position.y, p.z + a.position.z), mat_mul(&a.orientation, &b.orientation))
}
fn cf_inv(a: &CFrame) -> CFrame {
    let rt = a.orientation.transpose();
    let p = mat_vec(&rt, a.position);
    CFrame::new(Vector3::new(-p.x, -p.y, -p.z), rt)
}

fn transform_tree(dom: &mut WeakDom, root: Ref, t: &CFrame) {
    let refs: Vec<Ref> = dom.descendants_of(root).map(|i| i.referent()).collect();
    for r in refs {
        let inst = dom.get_by_ref_mut(r).unwrap();
        let class = inst.class.to_string();
        if BASEPART.contains(&class.as_str()) {
            if let Some(Variant::CFrame(cf)) = inst.properties.get_mut(&"CFrame".into()) { *cf = cf_mul(t, cf); }
        }
        if class == "Model" {
            if let Some(Variant::OptionalCFrame(Some(cf))) = inst.properties.get_mut(&"WorldPivotData".into()) { *cf = cf_mul(t, cf); }
            if let Some(Variant::CFrame(cf)) = inst.properties.get_mut(&"ModelMeshCFrame".into()) { *cf = cf_mul(t, cf); }
        }
    }
}

fn get_or_create(dom: &mut WeakDom, parent: Ref, class: &str, name: &str) -> Ref {
    if let Some(r) = child(dom, parent, name) { return r; }
    dom.insert(parent, InstanceBuilder::new(class).with_name(name))
}

fn pos_of(dom: &WeakDom, r: Ref) -> Vector3 { cframe_of(dom, r).position }

fn place_into(map: &str, pkg_path: &str, italy: &str, out: &str) {
    let mut dom = load(map);
    let pkg = load(pkg_path);
    let it = load(italy);

    // exact physical properties of the original game's track surfaces
    let it_pista = find(&it, "Workspace/Pista");
    let track_pp = it.get_by_ref(it_pista).unwrap().children().iter().copied().find_map(|c| {
        let i = it.get_by_ref(c).unwrap();
        if i.name == "Track" && i.class == "Part" && matches!(i.properties.get(&"CanCollide".into()), Some(Variant::Bool(true))) {
            i.properties.get(&"CustomPhysicalProperties".into()).cloned()
        } else { None }
    }).unwrap();
    // most common grass physics in the original map (35 parts): density 2.403, friction 2, elasticity 0.1, weights 0
    let it_grass = find(&it, "Workspace/Grass");
    let grass_pp = it.get_by_ref(it_grass).unwrap().children().iter().copied().find_map(|c| {
        match it.get_by_ref(c).unwrap().properties.get(&"CustomPhysicalProperties".into()) {
            Some(v @ Variant::PhysicalProperties(rbx_dom_weak::types::PhysicalProperties::Custom(cp))) if (cp.elasticity() - 0.1).abs() < 1e-6 => Some(v.clone()),
            _ => None,
        }
    }).unwrap();
    println!("track pp {:?}\ngrass pp {:?}", track_pp, grass_pp);

    let ws = find(&dom, "Workspace");
    // workspace settings as in the original game
    set_prop(&mut dom, ws, "StreamingEnabled", Variant::Bool(false));
    {
        let inst = dom.get_by_ref_mut(ws).unwrap();
        let mut attrs = match inst.properties.remove(&"Attributes".into()) { Some(Variant::Attributes(a)) => a, _ => Attributes::new() };
        attrs.insert("ChuvaType".to_string(), Variant::String("SUN".to_string()));
        inst.properties.insert("Attributes".into(), Variant::Attributes(attrs));
    }

    // drivable surfaces -> original track physics
    let mut counts: Vec<(String, usize)> = vec![];
    let groups: [(&str, &Variant); 6] = [
        ("Workspace/Spa/Pista/Superficie", &track_pp),
        ("Workspace/Spa/PitLane/Superficie", &track_pp),
        ("Workspace/Spa/PitLane/Entrada", &track_pp),
        ("Workspace/Spa/PitLane/Saida", &track_pp),
        ("Workspace/Spa/PitLane/AreaDosBoxes", &track_pp),
        ("Workspace/Spa/PitLane/Paddock", &track_pp),
    ];
    let terreno = find(&dom, "Workspace/Spa/Terreno");
    let mut all: Vec<(Ref, Variant)> = vec![];
    for (p, pp) in groups.iter() {
        let r = find(&dom, p);
        let n = dom.descendants_of(r).filter(|i| BASEPART.contains(&i.class.as_str())).map(|i| { all.push((i.referent(), (*pp).clone())); }).count();
        counts.push((p.to_string(), n));
    }
    let n = dom.descendants_of(terreno).filter(|i| BASEPART.contains(&i.class.as_str())
        && matches!(i.properties.get(&"CanCollide".into()), Some(Variant::Bool(true)) | None))
        .map(|i| { all.push((i.referent(), grass_pp.clone())); }).count();
    counts.push(("Workspace/Spa/Terreno (grama)".into(), n));
    for (r, pp) in all { set_prop(&mut dom, r, "CustomPhysicalProperties", pp); }
    println!("physics applied: {:?}", counts);

    // services
    let root = dom.root_ref();
    let rs = get_or_create(&mut dom, root, "ReplicatedStorage", "ReplicatedStorage");
    let sss = get_or_create(&mut dom, root, "ServerScriptService", "ServerScriptService");
    let ss = get_or_create(&mut dom, root, "ServerStorage", "ServerStorage");
    let sg = get_or_create(&mut dom, root, "StarterGui", "StarterGui");
    let sp = get_or_create(&mut dom, root, "StarterPlayer", "StarterPlayer");
    let spc = get_or_create(&mut dom, sp, "StarterCharacterScripts", "StarterCharacterScripts");
    let _sps = get_or_create(&mut dom, sp, "StarterPlayerScripts", "StarterPlayerScripts");

    let pf = |p: &str| find(&pkg, &format!("F1_Carro_Standalone/{p}"));
    let items: Vec<(Ref, Ref)> = vec![
        (pf("Workspace/Carro"), ws),
        (pf("ReplicatedStorage/EventsCar"), rs),
        (pf("ReplicatedStorage/ModuleCar"), rs),
        (pf("ServerScriptService/CarroStandalone"), sss),
        (pf("StarterGui/GUIcar"), sg),
        (pf("StarterGui/GUIMobileCar"), sg),
        (pf("StarterPlayer/StarterCharacterScripts/ScriptCarro"), spc),
        (pf("LEIA-ME"), ss),
    ];
    let srcs: Vec<Ref> = items.iter().map(|(s, _)| *s).collect();
    let clones = pkg.clone_multiple_into_external(&srcs, &mut dom);
    for (c, (_, dest)) in clones.iter().zip(items.iter()) { dom.transfer_within(*c, *dest); }
    let car = clones[0];

    // ---- put the car on grid slot 1, pointing in the race direction ----
    let g1 = find(&dom, "Workspace/Spa/Pista/Grid/GridPos01");
    let g3 = find(&dom, "Workspace/Spa/Pista/Grid/GridPos03");
    let (p1, p3) = (pos_of(&dom, g1), pos_of(&dom, g3));
    let (dx, dz) = (p1.x - p3.x, p1.z - p3.z);
    let l = (dx * dx + dz * dz).sqrt();
    let fwd = (dx / l, dz / l); // race direction (grid 3 -> grid 1)
    // car forward = from body centre towards the front wing, horizontal
    let corpo = find(&dom, "Workspace/Carro/Corpo");
    let asa = find(&dom, "Workspace/Carro/Corpo/AsaFrontal");
    let (pc, pa) = (pos_of(&dom, corpo), pos_of(&dom, asa));
    let (cx, cz) = (pa.x - pc.x, pa.z - pc.z);
    let cl = (cx * cx + cz * cz).sqrt();
    let carf = (cx / cl, cz / cl);
    // yaw angle rotating carf onto fwd (rotation about +Y: x' = x cos + z sin, z' = -x sin + z cos)
    let ang = (carf.0 * fwd.1 - carf.1 * fwd.0).atan2(carf.0 * fwd.0 + carf.1 * fwd.1);
    let theta = -ang;
    let (c, s) = (theta.cos(), theta.sin());
    let rot = Matrix3::new(Vector3::new(c, 0.0, s), Vector3::new(0.0, 1.0, 0.0), Vector3::new(-s, 0.0, c));
    let pivot = match dom.get_by_ref(car).unwrap().properties.get(&"WorldPivotData".into()) { Some(Variant::OptionalCFrame(Some(c))) => *c, _ => panic!() };
    // lowest wheel point relative to pivot height
    let mut min_y = f32::MAX;
    for w in ["Chassi/EixoFE/RodaFE", "Chassi/EixoFD/RodaFD", "Chassi/EixoT/RodaTD", "Chassi/EixoT/RodaTE"] {
        let r = find(&dom, &format!("Workspace/Carro/{w}"));
        min_y = min_y.min(pos_of(&dom, r).y - size_of(&dom, r).y / 2.0);
    }
    let pivot_above_wheels = pivot.position.y - min_y;
    // target: 12 studs behind the grid line of slot 1 (car body is ~23 studs long), on the surface
    let g1_top = p1.y + size_of(&dom, g1).y / 2.0;
    let target_pos = Vector3::new(p1.x - fwd.0 * 12.0, g1_top + 0.05 + pivot_above_wheels, p1.z - fwd.1 * 12.0);
    // T maps the old pivot to (target_pos, rot * old orientation)
    let target = CFrame::new(target_pos, mat_mul(&rot, &pivot.orientation));
    let t = cf_mul(&target, &cf_inv(&pivot));
    transform_tree(&mut dom, car, &t);
    let (pc2, pa2) = (pos_of(&dom, find(&dom, "Workspace/Carro/Corpo")), pos_of(&dom, find(&dom, "Workspace/Carro/Corpo/AsaFrontal")));
    let nf = ((pa2.x - pc2.x), (pa2.z - pc2.z));
    let nl = (nf.0 * nf.0 + nf.1 * nf.1).sqrt();
    println!("race dir {:?}; car forward after = ({:.4},{:.4}); grid1 {:?}; car pivot -> {:?}", fwd, nf.0 / nl, nf.1 / nl, p1, target_pos);

    let top = dom.root().children().to_vec();
    save(&dom, &top, out);
}

// ---------------------------------------------------------------------------
// chassis: add a chassis-only copy of the car next to the full one
// ---------------------------------------------------------------------------
use rbx_dom_weak::types::{BrickColor, Color3uint8};

fn rel_path(dom: &WeakDom, root: Ref, r: Ref) -> String {
    let mut names = vec![];
    let mut cur = r;
    while cur != root {
        let i = dom.get_by_ref(cur).unwrap();
        names.push(i.name.clone());
        cur = i.parent();
    }
    names.reverse();
    names.join("/")
}

fn set_attr(dom: &mut WeakDom, r: Ref, k: &str, v: Variant) {
    let inst = dom.get_by_ref_mut(r).unwrap();
    let mut a = match inst.properties.remove(&"Attributes".into()) { Some(Variant::Attributes(a)) => a, _ => Attributes::new() };
    a.insert(k.to_string(), v);
    inst.properties.insert("Attributes".into(), Variant::Attributes(a));
}

fn chassis(input: &str, srcdir: &str, out: &str) {
    let mut dom = load(input);
    let ws = find(&dom, "Workspace");
    let full = find(&dom, "Workspace/Carro");
    let car = dom.clone_within(full);
    dom.transfer_within(car, ws);
    // fresh ids for the copy
    let refs: Vec<Ref> = dom.descendants_of(car).map(|i| i.referent()).collect();
    for r in &refs { dom.get_by_ref_mut(*r).unwrap().properties.remove(&"UniqueId".into()); }
    dom.get_by_ref_mut(car).unwrap().name = "Carro_Chassi".to_string();
    let p = |dom: &WeakDom, rel: &str| -> Ref {
        let mut cur = car;
        for part in rel.split('/') { cur = child(dom, cur, part).unwrap_or_else(|| panic!("missing {rel}")); }
        cur
    };

    // ---------------- 1. remove ALL 3D models (MeshParts) ----------------
    let chassi_r = p(&dom, "Chassi");
    let corpo_r = p(&dom, "Corpo");
    // the slipstream target plate is a plain Part: keep it, hanging from the chassis (it is already welded to it)
    let vacuo = p(&dom, "Corpo/Vacuo");
    dom.transfer_within(vacuo, chassi_r);
    // cameras and RAY sensors are welded to Corpo, which was welded to Chassi: weld them straight to Chassi
    let welds: Vec<Ref> = dom.descendants_of(car).filter(|i| i.class == "WeldConstraint").map(|i| i.referent()).collect();
    for w in welds {
        for key in ["Part0", "Part1"] {
            let hit = matches!(dom.get_by_ref(w).unwrap().properties.get(&key.into()), Some(Variant::Ref(x)) if *x == corpo_r);
            if hit { set_prop(&mut dom, w, key, Variant::Ref(chassi_r)); }
        }
    }
    // attachment users before removal (to drop attachments left without any constraint)
    let att_users = |dom: &WeakDom| -> HashMap<Ref, usize> {
        let mut m = HashMap::new();
        for i in dom.descendants_of(car) {
            for key in ["Attachment0", "Attachment1"] {
                if let Some(Variant::Ref(a)) = i.properties.get(&key.into()) { if a.is_some() { *m.entry(*a).or_insert(0) += 1; } }
            }
        }
        m
    };
    let before = att_users(&dom);
    let remove = [
        "Corpo", "Chassi/Volante", "Maos",
        "Chassi/EixoFD/RodaFD/Pneu", "Chassi/EixoFE/RodaFE/Pneu", "Chassi/EixoT/RodaTD/Pneu", "Chassi/EixoT/RodaTE/Pneu",
        "Highlight",
    ];
    for rel in remove {
        let r = p(&dom, rel);
        let n: Vec<String> = dom.descendants_of(r).filter(|i| BASEPART.contains(&i.class.as_str())).map(|i| format!("{}[{}]", i.name, i.class)).collect();
        println!("remove {rel}: {:?}", n);
        dom.destroy(r);
    }
    let after = att_users(&dom);
    let orphans: Vec<Ref> = before.keys().filter(|a| dom.get_by_ref(**a).is_some() && !after.contains_key(*a)).copied().collect();
    for a in orphans {
        println!("remove orphan attachment {}", rel_path(&dom, car, a));
        dom.destroy(a);
    }
    // nothing left may point at a removed instance
    for i in dom.descendants_of(car) {
        for (k, v) in i.properties.iter() {
            if let Variant::Ref(x) = v { assert!(x.is_none() || dom.get_by_ref(*x).is_some(), "dangling {} on {}", k, i.name); }
        }
        assert!(i.class != "MeshPart", "MeshPart left: {}", i.name);
    }

    // ---------------- 2. server script for this copy ----------------
    let sc = p(&dom, "Chassi/ScriptCar");
    set_prop(&mut dom, sc, "Source", Variant::String(read_src(&format!("{srcdir}/ScriptCar_Chassi.server.lua"))));

    // ---------------- 3. clearer names for welds and attachments ----------------
    // (scripts never address welds or attachments by name; constraints reference them by Ref)
    let all: Vec<Ref> = dom.descendants_of(car).map(|i| i.referent()).collect();
    let mut users: HashMap<Ref, Vec<String>> = HashMap::new();
    for r in &all {
        let i = dom.get_by_ref(*r).unwrap();
        for key in ["Attachment0", "Attachment1"] {
            if let Some(Variant::Ref(a)) = i.properties.get(&key.into()) {
                if a.is_some() {
                    let parent = dom.get_by_ref(i.parent()).unwrap().name.clone();
                    users.entry(*a).or_default().push(format!("{}@{}", i.name, parent));
                }
            }
        }
    }
    let mut renamed = 0;
    for r in &all {
        let (class, old) = { let i = dom.get_by_ref(*r).unwrap(); (i.class.to_string(), i.name.clone()) };
        let new_name = if class == "WeldConstraint" {
            let i = dom.get_by_ref(*r).unwrap();
            let n = |k: &str| match i.properties.get(&k.into()) { Some(Variant::Ref(x)) if x.is_some() => dom.get_by_ref(*x).unwrap().name.clone(), _ => "?".into() };
            Some(format!("Solda_{}_{}", n("Part0"), n("Part1")))
        } else if class == "Attachment" {
            users.get(r).map(|u| format!("Att_{}", u.join("+")))
        } else { None };
        if let Some(nn) = new_name {
            if nn != old {
                set_attr(&mut dom, *r, "NomeOriginal", Variant::String(old));
                dom.get_by_ref_mut(*r).unwrap().name = nn;
                renamed += 1;
            }
        }
    }
    println!("renamed {renamed} welds/attachments");

    // ---------------- 4. colours by category (visual only: Color, Transparency, texture, constraint Visible/Color) ----------------
    let cats: [(&str, (u8, u8, u8)); 7] = [
        ("Chassi", (225, 225, 225)),
        ("Suporte", (255, 140, 0)),
        ("Suspensao", (255, 220, 0)),
        ("Direcao", (0, 110, 255)),
        ("Roda", (210, 30, 30)),
        ("Camera", (255, 0, 200)),
        ("OutraFisica", (0, 190, 90)),
    ];
    let color_of = |c: &str| cats.iter().find(|(n, _)| *n == c).unwrap().1;
    // (path, category, transparency)
    let parts: Vec<(&str, &str, f32)> = vec![
        ("Chassi", "Chassi", 0.0), ("Chassi/SeatM", "Chassi", 0.0),
        ("Chassi/EixoT", "Suporte", 0.0), ("Chassi/EixoFD", "Suporte", 0.0), ("Chassi/EixoFE", "Suporte", 0.0),
        ("Chassi/EixoFD/RodaFD", "Roda", 0.0), ("Chassi/EixoFE/RodaFE", "Roda", 0.0),
        ("Chassi/EixoT/RodaTD", "Roda", 0.0), ("Chassi/EixoT/RodaTE", "Roda", 0.0),
        ("Chassi/Cam1", "Camera", 0.3), ("Chassi/Cam2", "Camera", 0.3), ("Chassi/Cam3", "Camera", 0.3),
        ("Chassi/Cam4", "Camera", 0.3), ("Chassi/CamR", "Camera", 0.3),
        ("Chassi/RAYFD", "OutraFisica", 0.0), ("Chassi/RAYFE", "OutraFisica", 0.0), ("Chassi/RAYTD", "OutraFisica", 0.0),
        ("Chassi/RAYTE", "OutraFisica", 0.0), ("Chassi/RAYVACUO", "OutraFisica", 0.0),
        ("Chassi/Vacuo", "OutraFisica", 0.85), // placa que o vácuo de OUTRO carro detecta (sem colisão)
    ];
    for (rel, cat, tr) in &parts {
        let r = p(&dom, rel);
        let (cr, cg, cb) = color_of(cat);
        set_prop(&mut dom, r, "Color", Variant::Color3uint8(Color3uint8::new(cr, cg, cb)));
        set_prop(&mut dom, r, "Transparency", Variant::Float32(*tr));
        if dom.get_by_ref(r).unwrap().class == "MeshPart" {
            set_prop(&mut dom, r, "TextureContent", Variant::Content(Content::none()));
        }
        set_attr(&mut dom, r, "Categoria", Variant::String(cat.to_string()));
    }
    // every BasePart of the copy must have a category
    for d in dom.descendants_of(car) {
        if BASEPART.contains(&d.class.as_str()) {
            let path = rel_path(&dom, car, d.referent());
            assert!(parts.iter().any(|(rel, _, _)| *rel == path), "uncategorised part {path}");
        }
    }
    // springs (suspension) and steering hinges drawn in the world
    let constraints: Vec<(Ref, String)> = dom.descendants_of(car).filter(|i| i.class == "SpringConstraint" || i.class == "HingeConstraint")
        .map(|i| (i.referent(), i.name.clone())).collect();
    for (r, name) in constraints {
        let class = dom.get_by_ref(r).unwrap().class.to_string();
        if class == "SpringConstraint" {
            set_prop(&mut dom, r, "Visible", Variant::Bool(true));
            set_prop(&mut dom, r, "Color", Variant::BrickColor(BrickColor::NewYeller));
        } else if name == "direcao" {
            set_prop(&mut dom, r, "Visible", Variant::Bool(true));
            set_prop(&mut dom, r, "Color", Variant::BrickColor(BrickColor::BrightBlue));
        }
    }
    // colour legend
    let mut legend = Attributes::new();
    for (n, (cr, cg, cb)) in cats.iter() {
        legend.insert(n.to_string(), Variant::Color3(rbx_dom_weak::types::Color3::new(*cr as f32 / 255.0, *cg as f32 / 255.0, *cb as f32 / 255.0)));
    }
    dom.insert(car, InstanceBuilder::new("Configuration").with_name("LegendaCores").with_property("Attributes", legend));

    // ---------------- 5. place it on grid slot 2 (pure translation, same orientation) ----------------
    let g1 = find(&dom, "Workspace/Spa/Pista/Grid/GridPos01");
    let g2 = find(&dom, "Workspace/Spa/Pista/Grid/GridPos02");
    let (a, b) = (cframe_of(&dom, g1), cframe_of(&dom, g2));
    let d = Vector3::new(b.position.x - a.position.x, b.position.y - a.position.y, b.position.z - a.position.z);
    translate_tree(&mut dom, car, d);
    println!("chassis car translated by {:?}", d);

    let top = dom.root().children().to_vec();
    save(&dom, &top, out);
}

// blob: write a SharedString/BinaryString property to a file
fn blob(input: &str, path: &str, prop: &str, out: &str) {
    let dom = load(input);
    let r = find(&dom, path);
    match dom.get_by_ref(r).unwrap().properties.get(&prop.into()) {
        Some(Variant::SharedString(s)) => fs::write(out, s.data()).unwrap(),
        Some(Variant::BinaryString(b)) => fs::write(out, AsRef::<[u8]>::as_ref(b)).unwrap(),
        other => panic!("not a blob: {:?}", other.map(|v| v.ty())),
    }
}

// addscripts: <in> <out> then triples <TemplatePath> <DestParentPath> <Name> <SourceFile> ...
fn addscripts(a: &[String]) {
    let mut dom = load(&a[2]);
    let mut i = 4;
    while i + 3 < a.len() + 1 && i + 3 <= a.len() - 1 + 1 {
        if i + 3 > a.len() { break; }
        let tpl = find(&dom, &a[i]);
        let dest = find(&dom, &a[i + 1]);
        let c = clone_to(&mut dom, tpl, dest, &a[i + 2]);
        set_prop(&mut dom, c, "Source", Variant::String(read_src(&a[i + 3])));
        i += 4;
    }
    let top = dom.root().children().to_vec();
    save(&dom, &top, &a[3]);
}

// ---------------------------------------------------------------------------
// v2: chassi anti-pulo (mesma arquitetura, mesmos scripts) ao lado do original
// ---------------------------------------------------------------------------
use rbx_dom_weak::types::{CustomPhysicalProperties, PhysicalProperties};

// massa que sai de cada roda e vai para um lastro suspenso no mesmo ponto
const V2_DENS_RODA: f32 = 0.2; // original 0.7
const V2_DAMPING: f32 = 300.0; // original 99.3 frente / 198.6 trás
const V2_FREE_F: f64 = 1.541; // original 1.5 (compensa o lastro: mesma altura de rodagem)
const V2_FREE_T: f64 = 1.544;
const V2_LIM: f32 = 0.4986212; // mesmo curso, na ordem certa
const V2_LASTRO: f32 = 0.8; // aresta do cubo de lastro

fn custom_pp(dom: &WeakDom, r: Ref) -> Option<CustomPhysicalProperties> {
    match dom.get_by_ref(r).unwrap().properties.get(&"CustomPhysicalProperties".into()) {
        Some(Variant::PhysicalProperties(PhysicalProperties::Custom(c))) => Some(*c),
        _ => None,
    }
}

fn f32_prop(dom: &WeakDom, r: Ref, k: &str) -> f32 {
    match dom.get_by_ref(r).unwrap().properties.get(&k.into()) {
        Some(Variant::Float32(x)) => *x,
        other => panic!("{k}: {:?}", other),
    }
}

fn v2(input: &str, out: &str, mode: &str, model_out: Option<&str>) {
    let mut dom = load(input);
    let ws = find(&dom, "Workspace");
    let full = find(&dom, "Workspace/Carro");
    let car = clone_to(&mut dom, full, ws, "Carro_V2");
    let p = |dom: &WeakDom, rel: &str| -> Ref {
        let mut cur = car;
        for part in rel.split('/') { cur = child(dom, cur, part).unwrap_or_else(|| panic!("missing {rel}")); }
        cur
    };
    let mut log: Vec<String> = vec![];

    // 1. rodas: menos massa não suspensa, sem quique (elasticidade 0 com peso 1)
    let rodas = [("FD", "Chassi/EixoFD/RodaFD", "Chassi/EixoFD"), ("FE", "Chassi/EixoFE/RodaFE", "Chassi/EixoFE"),
                 ("TD", "Chassi/EixoT/RodaTD", "Chassi/EixoT"), ("TE", "Chassi/EixoT/RodaTE", "Chassi/EixoT")];
    let template = p(&dom, "Chassi/RAYFD");
    for (k, rr, er) in rodas {
        let roda = p(&dom, rr);
        let eixo = p(&dom, er);
        let sz = size_of(&dom, roda);
        let vol = std::f32::consts::PI * (sz.y / 2.0) * (sz.y / 2.0) * sz.x; // cilindro no eixo X
        let mut pp = custom_pp(&dom, roda).expect("roda sem CustomPhysicalProperties");
        let m_old = pp.density() * vol;
        pp.set_density(V2_DENS_RODA);
        pp.set_elasticity(0.0);
        pp.set_elasticity_weight(1.0);
        set_prop(&mut dom, roda, "CustomPhysicalProperties", Variant::PhysicalProperties(PhysicalProperties::Custom(pp)));
        let m_new = V2_DENS_RODA * vol;
        let dm = m_old - m_new;

        // 2. lastro com a massa tirada, no centro da roda, soldado à manga (frente) ou ao suporte traseiro
        let l = dom.clone_within(template);
        dom.transfer_within(l, eixo);
        let lr: Vec<Ref> = dom.descendants_of(l).map(|i| i.referent()).collect();
        for r in lr { dom.get_by_ref_mut(r).unwrap().properties.remove(&"UniqueId".into()); }
        dom.get_by_ref_mut(l).unwrap().name = format!("Lastro{k}");
        let a = V2_LASTRO;
        set_prop(&mut dom, l, "Size", Variant::Vector3(Vector3::new(a, a, a)));
        let rcf = cframe_of(&dom, roda);
        set_prop(&mut dom, l, "CFrame", Variant::CFrame(rcf));
        let dens = dm / (a * a * a);
        set_prop(&mut dom, l, "CustomPhysicalProperties", Variant::PhysicalProperties(PhysicalProperties::Custom(
            CustomPhysicalProperties::new(dens, 0.3, 0.0, 1.0, 1.0, 1.0))));
        set_prop(&mut dom, l, "Massless", Variant::Bool(false));
        set_prop(&mut dom, l, "CanCollide", Variant::Bool(false));
        set_prop(&mut dom, l, "CanTouch", Variant::Bool(false));
        set_prop(&mut dom, l, "CanQuery", Variant::Bool(false));
        set_prop(&mut dom, l, "Transparency", Variant::Float32(1.0));
        set_attr(&mut dom, l, "Categoria", Variant::String("LastroV2".into()));
        set_attr(&mut dom, l, "Massa", Variant::Float64(dm as f64));
        let weld = dom.get_by_ref(l).unwrap().children()[0];
        set_prop(&mut dom, weld, "Part0", Variant::Ref(l));
        set_prop(&mut dom, weld, "Part1", Variant::Ref(eixo));
        dom.get_by_ref_mut(weld).unwrap().name = format!("Solda_Lastro{k}");
        log.push(format!("roda {k}: massa {m_old:.3} -> {m_new:.3}; lastro {dm:.3} (densidade {dens:.4})"));
    }
    // a manga dianteira deixa de ser a raiz da montagem (o lastro é maior): mantém a massa dela
    for e in ["Chassi/EixoFD", "Chassi/EixoFE"] {
        let r = p(&dom, e);
        set_prop(&mut dom, r, "Massless", Variant::Bool(false));
    }

    // 3. amortecimento e 4. limites na ordem certa
    let molas = ["Chassi/EixoFD/RodaFD/SpringConstraint", "Chassi/EixoFE/RodaFE/SpringConstraint",
                 "Chassi/EixoT/RodaTD/Mola", "Chassi/EixoT/RodaTE/Mola"];
    for (i, m) in molas.iter().enumerate() {
        let r = p(&dom, m);
        let old = f32_prop(&dom, r, "Damping");
        set_prop(&mut dom, r, "Damping", Variant::Float32(V2_DAMPING));
        let fl = if i < 2 { V2_FREE_F } else { V2_FREE_T };
        set_prop(&mut dom, r, "FreeLength", Variant::Float32(fl as f32));
        log.push(format!("{m}: Damping {old} -> {V2_DAMPING}, FreeLength -> {fl}"));
    }
    for c in ["Chassi/EixoFD/MotorD", "Chassi/EixoFE/MotorE", "Chassi/EixoT/MotorD", "Chassi/EixoT/MotorE"] {
        let r = p(&dom, c);
        let (lo, up) = (f32_prop(&dom, r, "LowerLimit"), f32_prop(&dom, r, "UpperLimit"));
        set_prop(&mut dom, r, "LowerLimit", Variant::Float32(-V2_LIM));
        set_prop(&mut dom, r, "UpperLimit", Variant::Float32(V2_LIM));
        log.push(format!("{c}: limites {lo}/{up} -> {}/{}", -V2_LIM, V2_LIM));
    }

    // 5. peças da carroceria que colidem: sem quique (mesma densidade e atrito)
    for (b, def) in [("Corpo", None), ("Corpo/AsaFrontal", Some((0.7f32, 0.3f32))), ("Corpo/aerofolio", Some((0.7, 0.3)))] {
        let r = p(&dom, b);
        let mut pp = match custom_pp(&dom, r) {
            Some(c) => c,
            None => { let (d, f) = def.unwrap(); CustomPhysicalProperties::new(d, f, 0.5, 1.0, 1.0, 1.0) } // Plastic padrão
        };
        pp.set_elasticity(0.0);
        pp.set_elasticity_weight(1.0);
        set_prop(&mut dom, r, "CustomPhysicalProperties", Variant::PhysicalProperties(PhysicalProperties::Custom(pp)));
        log.push(format!("{b}: elasticidade -> 0"));
    }

    // 6. altura das molas aplicada pelo ScriptCar no spawn
    let cfg = p(&dom, "Config");
    set_attr(&mut dom, cfg, "MolalturaF", Variant::Float64(V2_FREE_F));
    set_attr(&mut dom, cfg, "MolalturaT", Variant::Float64(V2_FREE_T));
    set_attr(&mut dom, car, "Versao", Variant::String("V2 anti-pulo".into()));
    set_attr(&mut dom, car, "Base", Variant::String("Workspace.Carro (original)".into()));

    // posição
    let chassi = p(&dom, "Chassi");
    let d = match mode {
        "lab" => {
            let cf = cframe_of(&dom, chassi);
            let x = cf.orientation.x; // lado do carro
            Vector3::new(x.x * 12.0, 0.0, x.z * 12.0)
        }
        "spa" => {
            let (a, b) = (cframe_of(&dom, find(&dom, "Workspace/Spa/Pista/Grid/GridPos01")), cframe_of(&dom, find(&dom, "Workspace/Spa/Pista/Grid/GridPos02")));
            Vector3::new(b.position.x - a.position.x, b.position.y - a.position.y, b.position.z - a.position.z)
        }
        m if m.starts_with("grid:") => {
            // grid:<pasta do grid>:<N>  -> mesma posição relativa que o Carro tem no GridPos01
            let parts: Vec<&str> = m.splitn(3, ':').collect();
            let (a, b) = (cframe_of(&dom, find(&dom, &format!("{}/GridPos01", parts[1]))), cframe_of(&dom, find(&dom, &format!("{}/GridPos{:0>2}", parts[1], parts[2]))));
            Vector3::new(b.position.x - a.position.x, b.position.y - a.position.y, b.position.z - a.position.z)
        }
        _ => panic!("mode lab|spa|grid:<pasta>:<N>"),
    };
    translate_tree(&mut dom, car, d);
    log.push(format!("translação {:?}", d));
    for l in &log { println!("{l}"); }

    if let Some(mo) = model_out {
        save(&dom, &[car], mo);
    }
    let top = dom.root().children().to_vec();
    save(&dom, &top, out);
}
