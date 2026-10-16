import IncrementalWorkload.Base

namespace IncrementalWorkload

def unrelated (n : Nat) : Nat := n * n + 3

theorem leaf (n : Nat) : n = n := Eq.refl n

end IncrementalWorkload
