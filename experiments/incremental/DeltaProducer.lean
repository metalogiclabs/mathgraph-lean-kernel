/-
A narrow source-owned producer for the pinned qualification workload. The three application
module bodies are elaborated against one immutable Std import. This is not a general Lean
module loader. Authentication and source-file byte hashing belong to the Python issuer.
-/
import Lean
import LeanExport.Basic

open Lean LeanExport

namespace DeltaProducer

def sourcePaths : Array String := #["IncrementalWorkload/Base.lean",
  "IncrementalWorkload/Derived.lean", "IncrementalWorkload/Leaves.lean", "Workload.lean"]

def importPrefixes : Array String := #["import Std.Data.HashMap\n",
  "import IncrementalWorkload.Base\n", "import IncrementalWorkload.Base\n",
  "import IncrementalWorkload.Derived\nimport IncrementalWorkload.Leaves\n"]

def rootNames : List Name := [`IncrementalWorkload.early, `IncrementalWorkload.dependent,
  `IncrementalWorkload.dependent_spec, `Std.HashMap.getElem?_insert,
  `Std.HashMap.getElem?_erase, `IncrementalWorkload.unrelated, `IncrementalWorkload.leaf,
  `IncrementalWorkload.typed, `IncrementalWorkload.typed_identity]

def fail (msg : String) : IO α := throw <| IO.userError msg

def get (j : Json) (key : String) : IO Json :=
  match j.getObjVal? key with | .ok x => pure x | .error e => fail e

def string (j : Json) : IO String :=
  match j.getStr? with | .ok x => pure x | .error e => fail e

def strings (j : Json) : IO (Array String) := do
  match j.getArr? with
  | .ok xs => xs.mapM string
  | .error e => fail e

def readJson (s : String) : IO Json :=
  match Json.parse s with | .ok x => pure x | .error e => fail e

def emit (j : Json) : IO Unit := do
  let out ← IO.getStdout
  out.putStrLn j.compress
  out.flush

def elapsed (start : Nat) : IO Nat := return (← IO.monoNanosNow) - start

def nameJson (ns : Array Name) : Json := toJson <| ns.map toString

/-- Check all four source files, and remove only the fixed, known import prefixes. -/
def source (j : Json) : IO String := do
  let files ← get j "source_files"
  let .obj fields := files | fail "source_files must be an object"
  if fields.size != sourcePaths.size then fail "source_files must contain exactly the four pinned paths"
  let mut result := ""
  for path in sourcePaths, importPrefix in importPrefixes, i in [:sourcePaths.size] do
    let txt ← string (← get files path)
    unless txt.startsWith importPrefix do fail s!"unsupported import prefix: {path}"
    let body := (txt.drop importPrefix.length).toString
    for line in body.splitOn "\n" do
      let line := line.trimAscii.toString
      if line.startsWith "import " || line == "import" || line == "prelude" || line == "module" then
        fail s!"unsupported additional module command: {path}"
    if i < 3 then result := result ++ body ++ "\n"
    else
      for line in body.splitOn "\n" do
        let line := line.trimAscii.toString
        unless line.isEmpty || line.startsWith "--" do
          fail "Workload.lean may contain only the fixed imports and line comments"
  pure result

def localInfos (env : Environment) : Array (Name × ConstantInfo) :=
  env.constants.foldStage2 (fun acc n c => acc.push (n,c)) #[]

def build (base : Environment) (src : String) : IO Environment := do
  let err ← IO.getStderr
  let (env, msgs) ← IO.withStdout err <|
    Elab.process src (base.setMainModule `DeltaProbe) {} (some "DeltaProbe.lean")
  if msgs.hasErrors then
    let msgs ← msgs.toList.mapM (·.toString)
    fail <| "elaboration failed: " ++ String.intercalate "\n" msgs
  -- The source frontend must leave the imported constant map itself untouched.
  if env.constants.map₁.size != base.constants.map₁.size then fail "imported environment changed"
  pure env

/-- Only individual safe definitions and theorems with unchanged declaration metadata. -/
def compatible (a b : ConstantInfo) : Bool :=
  match a,b with
  | .defnInfo a, .defnInfo b =>
    a.name == b.name && a.levelParams == b.levelParams && a.hints == b.hints &&
    a.safety == b.safety && a.all == b.all && a.safety == .safe
  | .thmInfo a, .thmInfo b =>
    a.name == b.name && a.levelParams == b.levelParams && a.all == b.all
  | _, _ => false

structure Session where
  base : Environment
  baseline : Environment
  state : LeanExport.State
  roots : List Name
  profile : String
  revisionChain : Bool := false
  revision : Nat := 0

/-- Bounds allocations for this fixed workload; these maps still use copy-on-write on requests. -/
def initialState : LeanExport.State := {
  visitedNames := Std.HashMap.emptyWithCapacity 40000 |>.insert .anonymous 0
  visitedExprs := Std.HashMap.emptyWithCapacity 400000
  noMDataExprs := Std.HashMap.emptyWithCapacity 10000
}

unsafe def initializeSession (request : Json) : IO Session := do
  let src ← source request
  let revisionChain ← match request.getObjVal? "revision_chain" with
    | .error _ => pure false
    | .ok value => match value.getBool? with
      | .ok enabled => pure enabled
      | .error _ => fail "revision_chain must be a boolean"
  let roots ← strings (← get request "roots")
  let profile := request.getObjValD "profile" |>.getStr?.toOption |>.getD "original-v1"
  unless profile == "original-v1" || profile == "std-hashmap-expanded-v1" do fail "unsupported root profile"
  if profile == "original-v1" && roots.toList != rootNames.map toString then
    fail "unsupported roots or root order"
  if profile == "std-hashmap-expanded-v1" then
    if roots.toList.take rootNames.length != rootNames.map toString then fail "expanded roots must retain the original nine roots"
    let extra := roots.toList.drop rootNames.length
    if extra.isEmpty || extra != extra.mergeSort (· < ·) || extra.eraseDups != extra then
      fail "expanded extra roots must be sorted and unique"

  let path ← string (← get request "baseline_export")
  enableInitializersExecution
  let start ← IO.monoNanosNow
  let base ← importModules (loadExts := true) #[{ module := `Std.Data.HashMap }] {}
  let importNs ← elapsed start
  let actualRoots ← roots.toList.mapM fun str => do
    let some name := (Syntax.decodeNameLit ("`" ++ str)) | fail "invalid root name"
    if toString name != str then fail "noncanonical root name"
    pure name
  if profile == "std-hashmap-expanded-v1" then
    for name in actualRoots.drop rootNames.length do
      let str := toString name
      unless str.startsWith "Std.HashMap." || str.startsWith "Std.DHashMap." do fail "unsupported expanded root namespace"
      if rootNames.contains name || name.isInternal then fail "duplicate or internal expanded root"
      let some info := base.find? name | fail s!"expanded root is not in pinned Std import: {name}"
      if info.isUnsafe then fail s!"unsafe expanded root: {name}"
  let start ← IO.monoNanosNow
  let baseline ← build base src
  let elabNs ← elapsed start
  let infos := localInfos baseline
  if infos.size != 7 then fail "expected exactly seven local declarations"
  for name in rootNames.take 3 ++ rootNames.drop 5 do
    unless infos.any (fun pair => pair.1 == name) do fail s!"missing pinned local declaration: {name}"
  for (_,c) in infos do
    unless compatible c c do fail s!"unsupported baseline declaration kind: {c.name}"
  let start ← IO.monoNanosNow
  let (_, state) ← IO.FS.withFile path .write fun h =>
    IO.withStdout (.ofHandle h) <| StateT.run (s := initialState) <| ReaderT.run (r := {env := baseline}) do
      initState baseline
      dumpMetadata
      for n in actualRoots do dumpConstant n
  let exportNs ← elapsed start
  emit <| Json.mkObj ([("status", Json.str "ready"), ("baseline_export", toJson path),
    ("profile", toJson profile), ("roots", toJson roots),
    ("local_names", nameJson <| infos.map (·.1)),
    ("stats", Json.mkObj [("imported_constants", toJson base.constants.map₁.size),
      ("local_constants", toJson infos.size), ("exported_constants", toJson state.visitedConstants.size),
      ("dag_exprs", toJson state.visitedExprs.size)]),
    ("timings_ns", Json.mkObj [("import", toJson importNs), ("elaboration", toJson elabNs),
      ("baseline_export", toJson exportNs)])] ++
    if revisionChain then [("revision", toJson (0 : Nat))] else [])
  pure {base, baseline, state, roots := actualRoots, profile, revisionChain}

/-- In chain mode the caller must discard this speculative session after any
downstream refusal. Legacy mode retains the immutable genesis environment. -/
unsafe def handle (session : Session) (request : Json) : IO Session := do
  let src ← source request
  let start ← IO.monoNanosNow
  let env ← build session.base src
  let elabNs ← elapsed start
  unless ptrEq env.constants.map₁ session.baseline.constants.map₁ do
    fail "imported constant identity changed"
  let start ← IO.monoNanosNow
  let old := localInfos session.baseline
  let next := localInfos env
  if old.map (·.1) != next.map (·.1) then fail "local declaration schedule changed"
  let op := request.getObjValD "op" |>.getStr?.toOption |>.getD "delta"
  let mut changed : Array Name := #[]
  let mut unchanged := 0
  for (name, c) in next do
    let some prev := session.baseline.find? name | fail "new local declaration"
    if op != "fresh" && !(compatible prev c) then fail s!"declaration metadata/kind drift: {name}"
    if prev == c then unchanged := unchanged + 1
    else changed := changed.push name
  let compareNs ← elapsed start
  if op == "fresh" then
    let path ← string (← get request "export_path")
    let start ← IO.monoNanosNow
    IO.FS.withFile path .write fun h => IO.withStdout (.ofHandle h) <| dumpEnv env (some session.roots)
    emit <| Json.mkObj [("status", "fresh"), ("export_path", toJson path),
      ("changed_names", nameJson changed), ("timings_ns", Json.mkObj [
        ("elaboration", toJson elabNs), ("comparison", toJson compareNs), ("fresh_export", toJson (← elapsed start))])]
    return session
  if op != "delta" then fail "unsupported operation"
  let expected ← strings (← get request "expected_changed_names")
  let names := changed.map toString
  if expected.size != names.size || !(expected.all names.contains) || !(names.all expected.contains) then fail "expected_changed_names differs from complete local comparison"
  let path ← string (← get request "delta_path")
  let start ← IO.monoNanosNow
  let mut state := session.state
  for name in changed do state := {state with visitedConstants := state.visitedConstants.erase name}
  let (_, final) ← IO.FS.withFile path .write fun h =>
    IO.withStdout (.ofHandle h) <| StateT.run (s := state) <| ReaderT.run (r := {env}) do
      for name in changed do dumpConstant name
  let exportNs ← elapsed start
  emit <| Json.mkObj ([("status", Json.str "delta"), ("delta_path", toJson path),
    ("changed_names", nameJson changed), ("local_names", nameJson <| next.map (·.1)),
    ("stats", Json.mkObj [("compared_local_constants", toJson next.size),
      ("unchanged_local_constants", toJson unchanged), ("imported_identity_retained", true),
      ("new_exprs", toJson <| final.visitedExprs.size - session.state.visitedExprs.size),
      ("new_names", toJson <| final.visitedNames.size - session.state.visitedNames.size),
      ("new_levels", toJson <| final.visitedLevels.size - session.state.visitedLevels.size)]),
    ("timings_ns", Json.mkObj [("elaboration", toJson elabNs), ("comparison", toJson compareNs),
      ("delta_export", toJson exportNs)])] ++
    if session.revisionChain then [("revision", toJson (session.revision + 1))] else [])
  return if session.revisionChain then
    {session with baseline := env, state := final, revision := session.revision + 1}
  else session

unsafe def run (args : List String) : IO Unit := do
  let [initPath] := args | fail "usage: delta-producer INIT.json"
  initSearchPath (← findSysroot)
  let mut session ← initializeSession (← readJson (← IO.FS.readFile initPath))
  let input ← IO.getStdin
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    try session ← handle session (← readJson line)
    catch e =>
      emit <| Json.mkObj [("status", "error"), ("error", toJson e.toString)]
      -- No chain request may observe partially prepared exporter state after
      -- failure. The issuer reconstructs the last accepted source sequence.
      if session.revisionChain then IO.Process.exit 1

end DeltaProducer

unsafe def main (args : List String) : IO Unit := do
  try DeltaProducer.run args
  catch e =>
    DeltaProducer.emit <| Json.mkObj [("status", "error"), ("error", toJson e.toString)]
    IO.Process.exit 1
