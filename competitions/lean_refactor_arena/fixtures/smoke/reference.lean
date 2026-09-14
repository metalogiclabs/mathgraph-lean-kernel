theorem nat_add_zero_smoke (n : Nat) : n + 0 = n := by
  induction n with
  | zero =>
      rfl
  | succ n ih =>
      simp [ih]
