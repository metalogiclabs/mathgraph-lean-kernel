import IncrementalWorkload.Base

namespace IncrementalWorkload

def dependent (n : Nat) : Nat := n + early

theorem dependent_spec (n : Nat) : dependent n = n + early := rfl

theorem typed_identity : typed = typed := rfl

end IncrementalWorkload
