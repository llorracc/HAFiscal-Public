"""
Classes to solve and simulate consumption-savings model with a discrete, exogenous,
stochastic Markov state.  The only solver here extends ConsIndShockModel to
include a Markov state; the interest factor, permanent growth factor, and income
distribution can vary with the discrete state.
"""

import os
import warnings
import numpy as np
import scipy.sparse as sp
from copy import deepcopy

from HARK import AgentType
from HARK.ConsumptionSaving.LegacyOOsolvers import ConsIndShockSolver
from HARK.ConsumptionSaving.ConsIndShockModel import (
    ConsumerSolution,
    IndShockConsumerType,
    PerfForesightConsumerType,
    make_basic_CRRA_solution_terminal,
)
from HARK.ConsumptionSaving.ConsNewKeynesianModel import (
    NewKeynesianConsumerType as _NKConsumerType,
)
from HARK.distributions import MarkovProcess, Uniform, calc_expectation
from HARK.interpolation import (
    CubicInterp,
    LinearInterp,
    LowerEnvelope,
    MargValueFuncCRRA,
    ValueFuncCRRA,
)
from HARK.rewards import (
    CRRAutility,
    CRRAutility_inv,
    CRRAutility_invP,
    CRRAutilityP,
    CRRAutilityP_inv,
    CRRAutilityP_invP,
    CRRAutilityPP,
)

from HARK.utilities import (
    jump_to_grid_1D,
    jump_to_grid_2D,
    gen_tran_matrix_1D,
    gen_tran_matrix_2D
)

__all__ = ["ConsMarkovSolver", "MarkovConsumerType"]

utility = CRRAutility
utilityP = CRRAutilityP
utilityPP = CRRAutilityPP
utilityP_inv = CRRAutilityP_inv
utility_invP = CRRAutility_invP
utility_inv = CRRAutility_inv
utilityP_invP = CRRAutilityP_invP


_FASTEOP_DUMPED = False
_FASTEOP_ANNOUNCED = False


def _fast_EndOfPrdvP_cond(solver):
    """Fused replacement for the conditional ``calc_EndOfPrdvP`` hot path
    (Step-4 cure Lane B, plan 20260808-1030h): one searchsorted pass over
    the whole (aNrm x shock-atom) query tensor against the next cFunc's
    knots + direct CRRA powers, replacing the per-call HARK
    interpolator/utility dispatch chain. Replicates HARK's arithmetic
    exactly: mNext = R/(G*psi)*a + theta; clamped-searchsorted lerp on
    the LinearInterp knots; lower_extrap NaN mask; vP = c^(-rho) with
    the psi^(-rho) weight and DiscFacEff*R*G^(-rho) scaling. Returns
    None for any structure this does not replicate (cubic policies,
    decay/indexer/precomputed interpolants, non-scalar state params,
    non-2-row atoms) — the caller then runs the legacy path."""
    vpf = solver.vPfuncNext
    if type(vpf) is not MargValueFuncCRRA:
        return None
    func = vpf.cFunc
    if type(func) is not LinearInterp:
        return None
    if func.decay_extrap or getattr(func, "indexer", None) is not None \
            or hasattr(func, "slopes"):
        return None
    if getattr(solver, "CubicBool", False):
        return None
    d = solver.IncShkDstn
    atoms = np.asarray(d.atoms, dtype=float)
    pmv = np.asarray(d.pmv, dtype=float)
    if atoms.ndim != 2 or atoms.shape[0] != 2:
        return None
    perm, tran = atoms[0], atoms[1]
    a = np.asarray(solver.aNrmNow, dtype=float)
    R = float(solver.Rfree)
    G = float(solver.PermGroFac)
    rho = float(solver.CRRA)
    m = (R / (G * perm))[None, :] * a[:, None] + tran[None, :]  # (na, K)
    x = func.x_list
    y = func.y_list
    q = m.ravel()
    i = np.maximum(np.searchsorted(x[:-1], q), 1)
    alpha = (q - x[i - 1]) / (x[i] - x[i - 1])
    c = (1.0 - alpha) * y[i - 1] + alpha * y[i]
    if not func.lower_extrap:
        c[q < x[0]] = np.nan
    vP = c ** (-rho)
    w = (perm ** (-rho)) * pmv
    return (solver.DiscFacEff * R * G ** (-rho)
            * (vP.reshape(m.shape) @ w))


class ConsMarkovSolver(ConsIndShockSolver):
    """
    A class to solve a single period consumption-saving problem with risky income
    and stochastic transitions between discrete states, in a Markov fashion.
    Extends ConsIndShockSolver, with identical inputs but for a discrete
    Markov state, whose transition rule is summarized in MrkvArray.  Markov
    states can differ in their interest factor, permanent growth factor, live probability, and
    income distribution, so the inputs Rfree, PermGroFac, IncShkDstn, and LivPrb are
    now arrays or lists specifying those values in each (succeeding) Markov state.
    """

    def __init__(
        self,
        solution_next,
        IncShkDstn_list,
        LivPrb,
        DiscFac,
        CRRA,
        Rfree_list,
        PermGroFac_list,
        MrkvArray,
        BoroCnstArt,
        aXtraGrid,
        vFuncBool,
        CubicBool,
    ):
        """
        Constructor for a new solver for a one period problem with risky income
        and transitions between discrete Markov states.  In the descriptions below,
        N is the number of discrete states.

        Parameters
        ----------
        solution_next : ConsumerSolution
            The solution to next period's one period problem.
        IncShkDstn_list : [distribution.Distribution]
            A length N list of income distributions in each succeeding Markov
            state.  Each income distribution is a
            discrete approximation to the income process at the
            beginning of the succeeding period.
        LivPrb : np.array
            Survival probability; likelihood of being alive at the beginning of
            the succeeding period for each Markov state.
        DiscFac : float
            Intertemporal discount factor for future utility.
        CRRA : float
            Coefficient of relative risk aversion.
        Rfree_list : np.array
            Risk free interest factor on end-of-period assets for each Markov
            state in the succeeding period.
        PermGroFac_list : np.array
            Expected permanent income growth factor at the end of this period
            for each Markov state in the succeeding period.
        MrkvArray : np.array
            An NxN array representing a Markov transition matrix between discrete
            states.  The i,j-th element of MrkvArray is the probability of
            moving from state i in period t to state j in period t+1.
        BoroCnstArt: float or None
            Borrowing constraint for the minimum allowable assets to end the
            period with.  If it is less than the natural borrowing constraint,
            then it is irrelevant; BoroCnstArt=None indicates no artificial bor-
            rowing constraint.
        aXtraGrid: np.array
            Array of "extra" end-of-period asset values-- assets above the
            absolute minimum acceptable level.
        vFuncBool: boolean
            An indicator for whether the value function should be computed and
            included in the reported solution.
        CubicBool: boolean
            An indicator for whether the solver should use cubic or linear inter-
            polation.

        Returns
        -------
        None
        """
        # Set basic attributes of the problem

        self.solution_next = solution_next
        self.IncShkDstn_list = IncShkDstn_list
        self.LivPrb = LivPrb
        self.DiscFac = DiscFac
        self.CRRA = CRRA
        self.BoroCnstArt = BoroCnstArt
        self.aXtraGrid = aXtraGrid
        self.vFuncBool = vFuncBool
        self.CubicBool = CubicBool
        self.Rfree_list = Rfree_list
        self.PermGroFac_list = PermGroFac_list
        self.MrkvArray = MrkvArray
        self.StateCount = MrkvArray.shape[0]

        self.def_utility_funcs()

    def solve(self):
        """
        Solve the one period problem of the consumption-saving model with a Markov state.

        Parameters
        ----------
        none

        Returns
        -------
        solution : ConsumerSolution
            The solution to the single period consumption-saving problem. Includes
            a consumption function cFunc (using cubic or linear splines), a marg-
            inal value function vPfunc, a minimum acceptable level of normalized
            market resources mNrmMin, normalized human wealth hNrm, and bounding
            MPCs MPCmin and MPCmax.  It might also have a value function vFunc
            and marginal marginal value function vPPfunc.  All of these attributes
            are lists or arrays, with elements corresponding to the current
            Markov state.  E.g. solution.cFunc[0] is the consumption function
            when in the i=0 Markov state this period.
        """
        # Find the natural borrowing constraint in each current state
        self.def_boundary()

        # Initialize end-of-period (marginal) value functions
        self.EndOfPrdvFunc_list = []
        self.EndOfPrdvPfunc_list = []
        self.Ex_IncNextAll = (
            np.zeros(self.StateCount) + np.nan
        )  # expected income conditional on the next state
        self.WorstIncPrbAll = (
            np.zeros(self.StateCount) + np.nan
        )  # probability of getting the worst income shock in each next period state

        # Loop through each next-period-state and calculate the end-of-period
        # (marginal) value function
        for j in range(self.StateCount):
            # Condition values on next period's state (and record a couple for later use)
            self.condition_on_state(j)
            self.Ex_IncNextAll[j] = np.dot(
                self.ShkPrbsNext, self.PermShkValsNext * self.TranShkValsNext
            )
            self.WorstIncPrbAll[j] = self.WorstIncPrb

            # Construct the end-of-period marginal value function conditional
            # on next period's state and add it to the list of value functions
            EndOfPrdvPfunc_cond = self.make_EndOfPrdvPfuncCond()
            self.EndOfPrdvPfunc_list.append(EndOfPrdvPfunc_cond)

            # Construct the end-of-period value functional conditional on next
            # period's state and add it to the list of value functions
            if self.vFuncBool:
                EndOfPrdvFunc_cond = self.make_EndOfPrdvFuncCond()
                self.EndOfPrdvFunc_list.append(EndOfPrdvFunc_cond)

        # EndOfPrdvP_cond is EndOfPrdvP conditional on *next* period's state.
        # Take expectations to get EndOfPrdvP conditional on *this* period's state.
        self.calc_EndOfPrdvP()

        # Calculate the bounding MPCs and PDV of human wealth for each state
        self.calc_HumWealth_and_BoundingMPCs()

        # Find consumption and market resources corresponding to each end-of-period
        # assets point for each state (and add an additional point at the lower bound)
        aNrm = (
            np.asarray(self.aXtraGrid)[np.newaxis, :]
            + np.array(self.BoroCnstNat_list)[:, np.newaxis]
        )
        self.get_points_for_interpolation(self.EndOfPrdvP, aNrm)
        cNrm = np.hstack((np.zeros((self.StateCount, 1)), self.cNrmNow))
        mNrm = np.hstack(
            (np.reshape(self.mNrmMin_list, (self.StateCount, 1)), self.mNrmNow)
        )

        # Package and return the solution for this period
        self.BoroCnstNat = self.BoroCnstNat_list
        solution = self.make_solution(cNrm, mNrm)
        return solution

    def def_boundary(self):
        """
        Find the borrowing constraint for each current state and save it as an
        attribute of self for use by other methods.

        Parameters
        ----------
        none

        Returns
        -------
        none
        """
        self.BoroCnstNatAll = np.zeros(self.StateCount) + np.nan
        # Find the natural borrowing constraint conditional on next period's state
        for j in range(self.StateCount):
            PermShkMinNext = np.min(self.IncShkDstn_list[j].atoms[0])
            TranShkMinNext = np.min(self.IncShkDstn_list[j].atoms[1])
            self.BoroCnstNatAll[j] = (
                (self.solution_next.mNrmMin[j] - TranShkMinNext)
                * (self.PermGroFac_list[j] * PermShkMinNext)
                / self.Rfree_list[j]
            )

        self.BoroCnstNat_list = np.zeros(self.StateCount) + np.nan
        self.mNrmMin_list = np.zeros(self.StateCount) + np.nan
        self.BoroCnstDependency = np.zeros((self.StateCount, self.StateCount)) + np.nan
        # The natural borrowing constraint in each current state is the *highest*
        # among next-state-conditional natural borrowing constraints that could
        # occur from this current state.
        for i in range(self.StateCount):
            possible_next_states = self.MrkvArray[i, :] > 0
            self.BoroCnstNat_list[i] = np.max(self.BoroCnstNatAll[possible_next_states])

            # Explicitly handle the "None" case:
            if self.BoroCnstArt is None:
                self.mNrmMin_list[i] = self.BoroCnstNat_list[i]
            else:
                self.mNrmMin_list[i] = np.max(
                    [self.BoroCnstNat_list[i], self.BoroCnstArt]
                )
            self.BoroCnstDependency[i, :] = (
                self.BoroCnstNat_list[i] == self.BoroCnstNatAll
            )
        # Also creates a Boolean array indicating whether the natural borrowing
        # constraint *could* be hit when transitioning from i to j.

    def condition_on_state(self, state_index):
        """
        Temporarily assume that a particular Markov state will occur in the
        succeeding period, and condition solver attributes on this assumption.
        Allows the solver to construct the future-state-conditional marginal
        value function (etc) for that future state.

        Parameters
        ----------
        state_index : int
            Index of the future Markov state to condition on.

        Returns
        -------
        none
        """
        # Set future-state-conditional values as attributes of self
        self.IncShkDstn = self.IncShkDstn_list[state_index]
        self.Rfree = self.Rfree_list[state_index]
        self.PermGroFac = self.PermGroFac_list[state_index]
        self.vPfuncNext = self.solution_next.vPfunc[state_index]
        self.mNrmMinNow = self.mNrmMin_list[state_index]
        self.BoroCnstNat = self.BoroCnstNatAll[state_index]
        self.set_and_update_values(
            self.solution_next, self.IncShkDstn, self.LivPrb, self.DiscFac
        )
        self.DiscFacEff = (
            self.DiscFac
        )  # survival probability LivPrb represents probability from
        # *current* state, so DiscFacEff is just DiscFac for now

        # These lines have to come after set_and_update_values to override the definitions there
        self.vPfuncNext = self.solution_next.vPfunc[state_index]
        if self.CubicBool:
            self.vPPfuncNext = self.solution_next.vPPfunc[state_index]
        if self.vFuncBool:
            self.vFuncNext = self.solution_next.vFunc[state_index]

    def calc_EndOfPrdvPP(self):
        """
        Calculates end-of-period marginal marginal value using a pre-defined
        array of next period market resources in self.mNrmNext.

        Parameters
        ----------
        none

        Returns
        -------
        EndOfPrdvPP : np.array
            End-of-period marginal marginal value of assets at each value in
            the grid of assets.
        """

        def vpp_next(shocks, a_nrm, Rfree):
            return shocks["PermShk"] ** (-self.CRRA - 1.0) * self.vPPfuncNext(
                self.m_nrm_next(shocks, a_nrm, Rfree)
            )

        EndOfPrdvPP = (
            self.DiscFacEff
            * self.Rfree
            * self.Rfree
            * self.PermGroFac ** (-self.CRRA - 1.0)
            * self.IncShkDstn.expected(vpp_next, self.aNrmNow, self.Rfree)
        )
        return EndOfPrdvPP

    def make_EndOfPrdvFuncCond(self):
        """
        Construct the end-of-period value function conditional on next period's
        state.

        Parameters
        ----------
        EndOfPrdvP : np.array
            Array of end-of-period marginal value of assets corresponding to the
            asset values in self.aNrmNow.
        Returns
        -------
        none
        """

        def v_lvl_next(shocks, a_nrm, Rfree):
            return (
                shocks[0] ** (1.0 - self.CRRA) * self.PermGroFac ** (1.0 - self.CRRA)
            ) * self.vFuncNext(self.m_nrm_next(shocks, a_nrm, Rfree))

        EndOfPrdv_cond = self.DiscFacEff * calc_expectation(
            self.IncShkDstn, v_lvl_next, self.aNrmNow, self.Rfree
        )
        EndOfPrdvNvrs = self.u.inv(
            EndOfPrdv_cond
        )  # value transformed through inverse utility
        EndOfPrdvNvrsP = self.EndOfPrdvP_cond * self.u.derinv(
            EndOfPrdv_cond, order=(0, 1)
        )
        EndOfPrdvNvrs = np.insert(EndOfPrdvNvrs, 0, 0.0)
        EndOfPrdvNvrsP = np.insert(
            EndOfPrdvNvrsP, 0, EndOfPrdvNvrsP[0]
        )  # This is a very good approximation, vNvrsPP = 0 at the asset minimum
        aNrm_temp = np.insert(self.aNrmNow, 0, self.BoroCnstNat)
        EndOfPrdvNvrsFunc = CubicInterp(aNrm_temp, EndOfPrdvNvrs, EndOfPrdvNvrsP)
        EndOfPrdvFunc_dond = ValueFuncCRRA(EndOfPrdvNvrsFunc, self.CRRA)

        return EndOfPrdvFunc_dond

    def calc_EndOfPrdvPcond(self):
        """
        Calculate end-of-period marginal value of assets at each point in aNrmNow
        conditional on a particular state occuring in the next period.

        Step-4 cure Lane B (plan 20260808-1030h): the legacy path pays ~10
        HARK interpolator/utility dispatches per call across a 1.46M-call
        chain (profiled 1,455 s of Step 4's 64.5 min). The fused fast path
        replicates the SAME arithmetic in one vectorized pass; any
        structural surprise (cubic policies, decay/indexer/precomputed
        interpolants, non-2-row shock atoms) returns None and the legacy
        path runs. HAFISCAL_STEP4_FASTEOP: 1 (default) | off | verify
        (runs BOTH, prints the deviation, returns the legacy result).

        Parameters
        ----------
        None

        Returns
        -------
        EndOfPrdvP : np.array
            A 1D array of end-of-period marginal value of assets.
        """
        import os
        # History: this path's ~2.3e3 "discrepancy" vs legacy turned out
        # to be BUG-071 — the legacy labeled expected() was reading each
        # distribution's STALE xarray dataset (deepcopy severs the
        # atoms<->dataset aliasing), i.e. the WRONG shocks; this fused
        # path reads the intended atoms. Under the BUG-071 fix the two
        # agree at machine precision (max 3.45e-16 over sampled calls).
        # R2 EPILOGUE (2026-08-08 afternoon): default briefly ON per the
        # ruling, then REVERTED to OFF the same day — the run-scale A/B
        # refuted the speed premise (engagement PROVEN by the ACTIVE
        # print, wall 2,928.8 vs 2,922 s without: ~nothing; the profile's
        # 1,455 s cum was FLOPs this path still performs, not removable
        # dispatch). Numerically the paths are machine-precision equal
        # under the BUG-071 fix, so OFF is pure simplicity. 'verify'
        # remains the dual-run harness (it is what FOUND BUG-071).
        mode = os.environ.get("HAFISCAL_STEP4_FASTEOP", "0").strip().lower()
        if mode not in ("0", "off", "false"):
            try:
                fast = _fast_EndOfPrdvP_cond(self)
            except Exception:
                fast = None
            if fast is not None:
                global _FASTEOP_ANNOUNCED
                if not _FASTEOP_ANNOUNCED:
                    _FASTEOP_ANNOUNCED = True
                    print("[fasteop] fast path ACTIVE (first engagement)",
                          flush=True)
                if mode == "verify":
                    ref = ConsIndShockSolver.calc_EndOfPrdvP(self)
                    try:
                        fast2 = _fast_EndOfPrdvP_cond(self)
                    except Exception:
                        fast2 = None
                    dev = float(np.nanmax(
                        np.abs(fast - ref) / (1.0 + np.abs(ref))))
                    dev2 = (float(np.nanmax(
                        np.abs(fast2 - ref) / (1.0 + np.abs(ref))))
                        if fast2 is not None else float("nan"))
                    print(f"[fasteop-verify] dev={dev:.2e} dev_after={dev2:.2e}",
                          flush=True)
                    global _FASTEOP_DUMPED
                    if dev > 1e-8 and not _FASTEOP_DUMPED:
                        _FASTEOP_DUMPED = True
                        d = self.IncShkDstn
                        probe = np.linspace(-0.4, 3.0, 9)
                        np.savez("/tmp/claude-1000/-home-shared-github-llorracc-HAFiscal-Latest/a227ed17-1648-45f6-bd16-31aacaa4b28b/scratchpad/fasteop_dump.npz",
                                 fast=fast, ref=ref,
                                 aNrm=np.asarray(self.aNrmNow),
                                 atoms=np.asarray(d.atoms), pmv=np.asarray(d.pmv),
                                 x=self.vPfuncNext.cFunc.x_list,
                                 y=self.vPfuncNext.cFunc.y_list,
                                 probe=probe,
                                 vpf_direct=np.asarray(self.vPfuncNext(probe)),
                                 cfunc_direct=np.asarray(
                                     self.vPfuncNext.cFunc(probe)),
                                 scal=np.array([float(self.Rfree),
                                                float(self.PermGroFac),
                                                float(self.CRRA),
                                                float(self.DiscFacEff)]))
                        print("[fasteop-verify] state dumped", flush=True)
                    return ref
                return fast
        EndOfPrdvPcond = ConsIndShockSolver.calc_EndOfPrdvP(self)
        return EndOfPrdvPcond

    def make_EndOfPrdvPfuncCond(self):
        """
        Construct the end-of-period marginal value function conditional on next
        period's state.

        Parameters
        ----------
        None

        Returns
        -------
        EndofPrdvPfunc_cond : MargValueFuncCRRA
            The end-of-period marginal value function conditional on a particular
            state occuring in the succeeding period.
        """
        # Get data to construct the end-of-period marginal value function (conditional on next state)
        self.aNrm_cond = self.prepare_to_calc_EndOfPrdvP()
        self.EndOfPrdvP_cond = self.calc_EndOfPrdvPcond()
        EndOfPrdvPnvrs_cond = self.u.derinv(
            self.EndOfPrdvP_cond, order=(1, 0)
        )  # "decurved" marginal value
        if self.CubicBool:
            EndOfPrdvPP_cond = self.calc_EndOfPrdvPP()
            EndOfPrdvPnvrsP_cond = EndOfPrdvPP_cond * self.u.derinv(
                self.EndOfPrdvP_cond, order=(1, 1)
            )  # "decurved" marginal marginal value

        # Construct the end-of-period marginal value function conditional on the next state.
        if self.CubicBool:
            EndOfPrdvPnvrsFunc_cond = CubicInterp(
                self.aNrm_cond,
                EndOfPrdvPnvrs_cond,
                EndOfPrdvPnvrsP_cond,
                lower_extrap=True,
            )
        else:
            EndOfPrdvPnvrsFunc_cond = LinearInterp(
                self.aNrm_cond, EndOfPrdvPnvrs_cond, lower_extrap=True
            )
        EndofPrdvPfunc_cond = MargValueFuncCRRA(
            EndOfPrdvPnvrsFunc_cond, self.CRRA
        )  # "recurve" the interpolated marginal value function
        return EndofPrdvPfunc_cond

    def calc_EndOfPrdvP(self):
        """
        Calculates end of period marginal value (and marginal marginal) value
        at each aXtra gridpoint for each current state, unconditional on the
        future Markov state (i.e. weighting conditional end-of-period marginal
        value by transition probabilities).

        Parameters
        ----------
        none

        Returns
        -------
        none
        """
        # Find unique values of minimum acceptable end-of-period assets (and the
        # current period states for which they apply).
        aNrmMin_unique, state_inverse = np.unique(
            self.BoroCnstNat_list, return_inverse=True
        )
        self.possible_transitions = self.MrkvArray > 0

        # Calculate end-of-period marginal value (and marg marg value) at each
        # asset gridpoint for each current period state
        EndOfPrdvP = np.zeros((self.StateCount, self.aXtraGrid.size))
        EndOfPrdvPP = np.zeros((self.StateCount, self.aXtraGrid.size))
        for k in range(aNrmMin_unique.size):
            aNrmMin = aNrmMin_unique[k]  # minimum assets for this pass
            which_states = (
                state_inverse == k
            )  # the states for which this minimum applies
            aGrid = aNrmMin + self.aXtraGrid  # assets grid for this pass
            EndOfPrdvP_all = np.zeros((self.StateCount, self.aXtraGrid.size))
            EndOfPrdvPP_all = np.zeros((self.StateCount, self.aXtraGrid.size))
            for j in range(self.StateCount):
                if np.any(
                    np.logical_and(self.possible_transitions[:, j], which_states)
                ):  # only consider a future state if one of the relevant states could transition to it
                    EndOfPrdvP_all[j, :] = self.EndOfPrdvPfunc_list[j](aGrid)
                    if (
                        self.CubicBool
                    ):  # Add conditional end-of-period (marginal) marginal value to the arrays
                        EndOfPrdvPP_all[j, :] = self.EndOfPrdvPfunc_list[j].derivativeX(
                            aGrid
                        )
            # Weight conditional marginal (marginal) values by transition probs
            # to get unconditional marginal (marginal) value at each gridpoint.
            EndOfPrdvP_temp = np.dot(self.MrkvArray, EndOfPrdvP_all)
            EndOfPrdvP[which_states, :] = EndOfPrdvP_temp[
                which_states, :
            ]  # only take the states for which this asset minimum applies
            if self.CubicBool:
                EndOfPrdvPP_temp = np.dot(self.MrkvArray, EndOfPrdvPP_all)
                EndOfPrdvPP[which_states, :] = EndOfPrdvPP_temp[which_states, :]

        # Store the results as attributes of self, scaling end of period marginal value by survival probability from each current state
        LivPrb_tiled = np.tile(
            np.reshape(self.LivPrb, (self.StateCount, 1)), (1, self.aXtraGrid.size)
        )
        self.EndOfPrdvP = LivPrb_tiled * EndOfPrdvP
        if self.CubicBool:
            self.EndOfPrdvPP = LivPrb_tiled * EndOfPrdvPP

    def calc_HumWealth_and_BoundingMPCs(self):
        """
        Calculates human wealth and the maximum and minimum MPC for each current
        period state, then stores them as attributes of self for use by other methods.

        Parameters
        ----------
        none

        Returns
        -------
        none
        """
        # Upper bound on MPC at lower m-bound
        WorstIncPrb_array = self.BoroCnstDependency * np.tile(
            np.reshape(self.WorstIncPrbAll, (1, self.StateCount)), (self.StateCount, 1)
        )
        temp_array = self.MrkvArray * WorstIncPrb_array
        WorstIncPrbNow = np.sum(
            temp_array, axis=1
        )  # Probability of getting the "worst" income shock and transition from each current state
        ExMPCmaxNext = (
            np.dot(
                temp_array,
                self.Rfree_list ** (1.0 - self.CRRA)
                * self.solution_next.MPCmax ** (-self.CRRA),
            )
            / WorstIncPrbNow
        ) ** (-1.0 / self.CRRA)
        DiscFacEff_temp = self.DiscFac * self.LivPrb
        self.MPCmaxNow = 1.0 / (
            1.0
            + ((DiscFacEff_temp * WorstIncPrbNow) ** (1.0 / self.CRRA)) / ExMPCmaxNext
        )
        self.MPCmaxEff = self.MPCmaxNow
        self.MPCmaxEff[self.BoroCnstNat_list < self.mNrmMin_list] = 1.0
        # State-conditional PDV of human wealth
        hNrmPlusIncNext = self.Ex_IncNextAll + self.solution_next.hNrm
        self.hNrmNow = np.dot(
            self.MrkvArray, (self.PermGroFac_list / self.Rfree_list) * hNrmPlusIncNext
        )
        # Lower bound on MPC as m gets arbitrarily large
        temp = (
            DiscFacEff_temp
            * np.dot(
                self.MrkvArray,
                self.solution_next.MPCmin ** (-self.CRRA)
                * self.Rfree_list ** (1.0 - self.CRRA),
            )
        ) ** (1.0 / self.CRRA)
        self.MPCminNow = 1.0 / (1.0 + temp)

    def make_solution(self, cNrm, mNrm):
        """
        Construct an object representing the solution to this period's problem.

        Parameters
        ----------
        cNrm : np.array
            Array of normalized consumption values for interpolation.  Each row
            corresponds to a Markov state for this period.
        mNrm : np.array
            Array of normalized market resource values for interpolation.  Each
            row corresponds to a Markov state for this period.

        Returns
        -------
        solution : ConsumerSolution
            The solution to the single period consumption-saving problem. Includes
            a consumption function cFunc (using cubic or linear splines), a marg-
            inal value function vPfunc, a minimum acceptable level of normalized
            market resources mNrmMin, normalized human wealth hNrm, and bounding
            MPCs MPCmin and MPCmax.  It might also have a value function vFunc
            and marginal marginal value function vPPfunc.  All of these attributes
            are lists or arrays, with elements corresponding to the current
            Markov state.  E.g. solution.cFunc[0] is the consumption function
            when in the i=0 Markov state this period.
        """
        solution = (
            ConsumerSolution()
        )  # An empty solution to which we'll add state-conditional solutions
        # Calculate the MPC at each market resource gridpoint in each state (if desired)
        if self.CubicBool:
            dcda = self.EndOfPrdvPP / self.u.der(np.array(self.cNrmNow), order=2)
            MPC = dcda / (dcda + 1.0)
            self.MPC_temp = np.hstack(
                (np.reshape(self.MPCmaxNow, (self.StateCount, 1)), MPC)
            )
            interpfunc = self.make_cubic_cFunc
        else:
            interpfunc = self.make_linear_cFunc

        # Loop through each current period state and add its solution to the overall solution
        for i in range(self.StateCount):
            # Set current-period-conditional human wealth and MPC bounds
            self.hNrmNow_j = self.hNrmNow[i]
            self.MPCminNow_j = self.MPCminNow[i]
            if self.CubicBool:
                self.MPC_temp_j = self.MPC_temp[i, :]

            # Construct the consumption function by combining the constrained and unconstrained portions
            self.cFuncNowCnst = LinearInterp(
                [self.mNrmMin_list[i], self.mNrmMin_list[i] + 1.0], [0.0, 1.0]
            )
            cFuncNowUnc = interpfunc(mNrm[i, :], cNrm[i, :])
            cFuncNow = LowerEnvelope(cFuncNowUnc, self.cFuncNowCnst)

            # Make the marginal value function and pack up the current-state-conditional solution
            vPfuncNow = MargValueFuncCRRA(cFuncNow, self.CRRA)
            solution_cond = ConsumerSolution(
                cFunc=cFuncNow, vPfunc=vPfuncNow, mNrmMin=self.mNrmMinNow
            )
            if (
                self.CubicBool
            ):  # Add the state-conditional marginal marginal value function (if desired)
                solution_cond = self.add_vPPfunc(solution_cond)

            # Add the current-state-conditional solution to the overall period solution
            solution.append_solution(solution_cond)

        # Add the lower bounds of market resources, MPC limits, human resources,
        # and the value functions to the overall solution
        solution.mNrmMin = self.mNrmMin_list
        solution = self.add_MPC_and_human_wealth(solution)
        if self.vFuncBool:
            vFuncNow = self.make_vFunc(solution)
            solution.vFunc = vFuncNow

        # Return the overall solution to this period
        return solution

    def make_linear_cFunc(self, mNrm, cNrm):
        """
        Make a linear interpolation to represent the (unconstrained) consumption
        function conditional on the current period state.

        Parameters
        ----------
        mNrm : np.array
            Array of normalized market resource values for interpolation.
        cNrm : np.array
            Array of normalized consumption values for interpolation.

        Returns
        -------
        cFuncUnc: an instance of HARK.interpolation.LinearInterp
        """
        # BUG-106 (2026-08-30): use the SAME above-grid tail the PE model attaches, selected by the SAME SST
        # predicate (`grid_sizing.powerlaw_form_active`, via `powerlaw_decay.decay_linear_ctor`) that
        # `AggFiscalModel.solve_agg_cons_markov_alt` uses. Before this the two solvers built one object by two
        # methods: the PE attached the measured power-law decay, this solver HARK's plain linear PF asymptote —
        # measured divergence 0.15 % of consumption at the solve-grid top and 0.3-0.4 % above it, on the GIC-cap
        # atom that holds 12 % of college wealth above that top. Limits are unchanged (the solver's own hNrm and
        # MPCmin); only the FORM of the extrapolation is now shared. `HAFISCAL_PF_DECAY_EXTRAP=0|exp` selects
        # HARK's LinearInterp exactly as before.
        # Q1 (dual-path sweep 2026-09-02 §4; Phase-2 brief 2026-09-03 — MEASUREMENT candidate, not adopted): the
        # EXPONENT is now shared too. The measured two-secant Q from the solved knots is passed as `decay_extrap_Q`
        # exactly as the PE attach passes it; before this the constructor derived Q from the top segment's
        # level+slope pair — the residual `step4/pe_anchor_gate.EXPECTED['cFunc/cap_atom']` declares. mNrm[0]/cNrm[0]
        # is the synthetic (mNrmMin, 0) knot `solve()` prepends, so the estimator sees the solved knots only (the
        # PE's `m_temp[1:]`); the limits stay the solver's own (hNrm_j, MPCmin_j), the pair the estimator's PF line uses.
        from powerlaw_decay import decay_linear_ctor, measured_tail_q_kwargs
        cFuncUnc = decay_linear_ctor()(
            mNrm, cNrm, self.MPCminNow_j * self.hNrmNow_j, self.MPCminNow_j,
            **measured_tail_q_kwargs(mNrm[1:], cNrm[1:], self.hNrmNow_j, self.MPCminNow_j),
        )
        return cFuncUnc

    def make_cubic_cFunc(self, mNrm, cNrm):
        """
        Make a cubic interpolation to represent the (unconstrained) consumption
        function conditional on the current period state.

        Parameters
        ----------
        mNrm : np.array
            Array of normalized market resource values for interpolation.
        cNrm : np.array
            Array of normalized consumption values for interpolation.

        Returns
        -------
        cFuncUnc: an instance of HARK.interpolation.CubicInterp
        """
        # BUG-106: the cubic twin of the linear branch above — same shared selection, same reason. Q1 (2026-09-03,
        # MEASUREMENT candidate): the same measured exponent, passed the same way.
        from powerlaw_decay import decay_cubic_ctor, measured_tail_q_kwargs
        cFuncUnc = decay_cubic_ctor()(
            mNrm,
            cNrm,
            self.MPC_temp_j,
            self.MPCminNow_j * self.hNrmNow_j,
            self.MPCminNow_j,
            **measured_tail_q_kwargs(mNrm[1:], cNrm[1:], self.hNrmNow_j, self.MPCminNow_j),
        )
        return cFuncUnc

    def make_vFunc(self, solution):
        """
        Construct the value function for each current state.

        Parameters
        ----------
        solution : ConsumerSolution
            The solution to the single period consumption-saving problem. Must
            have a consumption function cFunc (using cubic or linear splines) as
            a list with elements corresponding to the current Markov state.  E.g.
            solution.cFunc[0] is the consumption function when in the i=0 Markov
            state this period.

        Returns
        -------
        vFuncNow : [ValueFuncCRRA]
            A list of value functions (defined over normalized market resources
            m) for each current period Markov state.
        """
        vFuncNow = []  # Initialize an empty list of value functions
        # Loop over each current period state and construct the value function
        for i in range(self.StateCount):
            # Make state-conditional grids of market resources and consumption
            mNrmMin = self.mNrmMin_list[i]
            mGrid = mNrmMin + self.aXtraGrid
            cGrid = solution.cFunc[i](mGrid)
            aGrid = mGrid - cGrid

            # Calculate end-of-period value at each gridpoint
            EndOfPrdv_all = np.zeros((self.StateCount, self.aXtraGrid.size))
            for j in range(self.StateCount):
                if self.possible_transitions[i, j]:
                    EndOfPrdv_all[j, :] = self.EndOfPrdvFunc_list[j](aGrid)
            EndOfPrdv = np.dot(self.MrkvArray[i, :], EndOfPrdv_all)

            # Calculate (normalized) value and marginal value at each gridpoint
            vNrmNow = self.u(cGrid) + EndOfPrdv
            vPnow = self.u.der(cGrid)

            # Make a "decurved" value function with the inverse utility function
            # value transformed through inverse utility
            vNvrs = self.u.inv(vNrmNow)
            vNvrsP = vPnow * self.u.derinv(vNrmNow, order=(0, 1))
            mNrm_temp = np.insert(mGrid, 0, mNrmMin)  # add the lower bound
            vNvrs = np.insert(vNvrs, 0, 0.0)
            vNvrsP = np.insert(
                vNvrsP, 0, self.MPCmaxEff[i] ** (-self.CRRA / (1.0 - self.CRRA))
            )
            MPCminNvrs = self.MPCminNow[i] ** (-self.CRRA / (1.0 - self.CRRA))
            vNvrsFunc_i = CubicInterp(
                mNrm_temp, vNvrs, vNvrsP, MPCminNvrs * self.hNrmNow[i], MPCminNvrs
            )

            # "Recurve" the decurved value function and add it to the list
            vFunc_i = ValueFuncCRRA(vNvrsFunc_i, self.CRRA)
            vFuncNow.append(vFunc_i)
        return vFuncNow


_FAST_TRANMAT_MOD = None
_FAST_TRANMAT_ANNOUNCED = False


def _tranmat_mod():
    """Lazy loader for Code/HA-Models/step4_fast_tranmat: the L3a batched
    kernel AND (BUG-097, 2026-08-28) the single source of the
    HAFISCAL_STEP4_TRANMAT_GROWTH toggle + the per-next-state PermGroFac
    every transition builder divides by (`permgrofac_next`), so the kernel
    and the legacy loops in calc_transition_matrix cannot disagree on Gamma.
    A failed import raises (the toggle SST must be present)."""
    global _FAST_TRANMAT_MOD
    if _FAST_TRANMAT_MOD is None:
        import os as _os
        import sys as _sys
        _parent = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
        if _parent not in _sys.path:
            _sys.path.insert(0, _parent)
        import step4_fast_tranmat as _mod
        _FAST_TRANMAT_MOD = _mod
    return _FAST_TRANMAT_MOD


_PWSURV_MOD = None


def _pweighted_survival():
    """Lazy import of the p-weighted survival SST (Code/HA-Models/pweighted_survival.py), the ONE
    definition of the survivor/newborn split under mortality + growth (BUG-108). Lazy and
    path-inserting for the same reason `_tranmat_mod` is: this module is imported from
    FromPandemicCode, whose parent is not always on sys.path at import time. A failed import RAISES
    -- a silent fallback to LivPrb is precisely the bug."""
    global _PWSURV_MOD
    if _PWSURV_MOD is None:
        import os as _os
        import sys as _sys
        _parent = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
        if _parent not in _sys.path:
            _sys.path.insert(0, _parent)
        import pweighted_survival as _mod
        _PWSURV_MOD = _mod
    return _PWSURV_MOD


def _newborn_m_vector(tran_shks_mp):
    """The newborn's market-resources vector for one destination state.
    DELEGATES to the SST `step4_fast_tranmat.newborn_m_values` (the same
    resolver the batched kernel consumes), so the python loop and the
    kernel cannot disagree on HAFISCAL_HANK_NEWBORN_M. See the SST's
    docstring for the modes (unit | income | float) and the scoping
    (defaults resolved in step4/hh_setup; PE consumers get `unit`)."""
    return _tranmat_mod().newborn_m_values(tran_shks_mp)


def _place_tran_block_1D(tran_mat, m, mp, mrkv_mmp, dist_mGrid, bNext_over_G, shk_prbs, perm_shks,
                         tran_shks, w_surv, J_phase):
    """One (m -> mp) block of the 1D (Harmenberg) transition matrix, shared by the infinite- and the
    finite-horizon python loops of calc_transition_matrix.

    `w_surv` is the p-weighted SURVIVOR WEIGHT for this destination state, from the single source of
    truth `pweighted_survival.survivor_weight(LivPrb, PermGroFac[mp])` (BUG-108). It is NOT LivPrb:
    under a p-weighted measure with mortality AND growth the surviving mass carries LivPrb*Gamma and
    newborns the complement, because the incumbent stock of permanent income grows every period while
    newborns always arrive at p = 1. This function does no arithmetic on it beyond the single
    `1 - w_surv` that `gen_tran_matrix_1D` forms internally -- the numba twin forms the same
    complement from the same float -- so the two builders cannot drift by grouping a product
    differently. At Gamma == 1 the SST returns LivPrb exactly, so the build is byte-identical to the
    pre-BUG-108 one.

    Legacy (J_phase == 0): tran_mat[mp, :, m, :] = mrkv[m, mp] * gen_tran_matrix_1D(..., w_surv, NewBornDist) —
    the survivors' lottery plus the newborn mass at m = 1 in the SAME state mp (HARK's convention: a newborn
    takes the chain transition of the household it replaces).

    Earnings phase (J_phase > 0; step4_fast_tranmat.newborn_phase_J): matured (mp >= J_phase) is absorbing,
    and newborns are born GROWING (the PE model's rule; without the reset the ergodic distribution is
    all-matured). So for a matured destination the survivors' mass stays in mp (NewBornDist = 0: x + 0.0 == x
    exactly) and the newborn mass is added to the growing image mp - J_phase with that state's own shock
    probabilities — the same assign-then-add order the L3a/L3b kernel uses (bitwise-equal).
    """
    NewBornDist = jump_to_grid_1D(_newborn_m_vector(tran_shks[mp]), shk_prbs[mp], dist_mGrid)
    if J_phase > 0 and mp >= J_phase:
        mg = mp - J_phase
        tran_mat[mp, :, m, :] = mrkv_mmp * gen_tran_matrix_1D(dist_mGrid, bNext_over_G, shk_prbs[mp],
                                                              perm_shks[mp], tran_shks[mp], w_surv,
                                                              np.zeros_like(NewBornDist))
        NewBornDist_g = jump_to_grid_1D(_newborn_m_vector(tran_shks[mg]), shk_prbs[mg], dist_mGrid)
        tran_mat[mg, :, m, :] += mrkv_mmp * ((1.0 - w_surv) * NewBornDist_g)[:, None]
    else:
        tran_mat[mp, :, m, :] = mrkv_mmp * gen_tran_matrix_1D(dist_mGrid, bNext_over_G, shk_prbs[mp],
                                                              perm_shks[mp], tran_shks[mp], w_surv,
                                                              NewBornDist)


def _finite_tranmat_fast(agent, shk_dstn):
    """L3a fast path for the finite-horizon 1D transition-matrix stage
    (plans/20260808-1638h): one batched numba call per agent instead of
    ~3,600 per-(t, markov-pair) launches. Bitwise-equal arithmetic (same
    expression trees and accumulation order as gen_tran_matrix_1D +
    jump_to_grid_1D). Returns True when it handled the build (setting
    cPol_Grid/aPol_Grid/tran_matrix); False -> caller runs the legacy
    loop. Guards: env flag, per-period len-1 pGrid (Harmenberg), uniform
    shock-atom count across states/periods.
    """
    global _FAST_TRANMAT_ANNOUNCED
    import os as _os
    if _os.environ.get("HAFISCAL_STEP4_FAST_TRANMAT", "1").strip().lower() in ("0", "off", "false"):
        return False
    try:
        _mod = _tranmat_mod()

        bigT = agent.T_cycle
        dist_mGrid = agent.dist_mGrid
        n_m = len(agent.MrkvArray[0])
        n_a = dist_mGrid.size

        # structural guards (any mismatch -> legacy)
        if isinstance(agent.dist_pGrid, list):
            if len(agent.dist_pGrid) != bigT or any(len(g) != 1 for g in agent.dist_pGrid):
                return False
        elif len(agent.dist_pGrid) != 1:
            return False
        K = len(shk_dstn[0][0].pmv)
        for t in (0, bigT - 1):
            for m in range(n_m):
                d = shk_dstn[t][m]
                if len(d.pmv) != K or np.shape(d.atoms) != (2, K):
                    return False

        cPol = np.zeros((bigT, n_m, n_a))
        aPol = np.zeros((bigT, n_m, n_a))
        bNext_t = np.zeros((bigT, n_m, n_a))
        gro_t = np.zeros((bigT, n_m))
        prbs_t = np.zeros((bigT, n_m, K))
        perm_t = np.zeros((bigT, n_m, K))
        tran_t = np.zeros((bigT, n_m, K))
        liv_t = np.zeros(bigT)
        mrkv_t = np.zeros((bigT, n_m, n_m))
        # earnings phase: newborns of a matured destination are born growing (0 = no phase)
        J_phase = _mod.newborn_phase_J(agent, n_m)
        for t in range(bigT):
            Rfree = agent.Rfree[t]
            # BUG-097: the growth factor of the state transitioned INTO
            gro_t[t] = _mod.permgrofac_next(agent, t, n_m)
            for m in range(n_m):
                cPol[t][m] = agent.solution[t].cFunc[m](dist_mGrid)
                aPol[t][m] = dist_mGrid - cPol[t][m]
                bNext_t[t][m] = Rfree[m] * aPol[t][m]
                d = shk_dstn[t][m]
                if len(d.pmv) != K:
                    return False
                prbs_t[t][m] = d.pmv
                tran_t[t][m] = d.atoms[1]
                perm_t[t][m] = d.atoms[0]
            liv_t[t] = agent.LivPrb[t][0]
            mrkv_t[t] = agent.MrkvArray[t]

        block = _mod.build_finite_tranmat_1D(
            dist_mGrid, bNext_t, prbs_t, perm_t, tran_t, liv_t, mrkv_t,
            gro_t=gro_t, J_phase=J_phase)
        agent.cPol_Grid = cPol
        agent.aPol_Grid = aPol
        agent.tran_matrix = [block[t] for t in range(bigT)]
        if not _FAST_TRANMAT_ANNOUNCED:
            _FAST_TRANMAT_ANNOUNCED = True
            print("[fast_tranmat] batched finite-horizon transition matrices ACTIVE")
        return True
    except Exception as e:
        print(f"[fast_tranmat] fallback to legacy loop: {type(e).__name__}: {e}")
        return False


def _solve_ConsMarkov(
    solution_next,
    IncShkDstn,
    LivPrb,
    DiscFac,
    CRRA,
    Rfree,
    PermGroFac,
    MrkvArray,
    BoroCnstArt,
    aXtraGrid,
    vFuncBool,
    CubicBool,
):
    """
    Solves a single period consumption-saving problem with risky income and
    stochastic transitions between discrete states, in a Markov fashion.  Has
    identical inputs as solveConsIndShock, except for a discrete
    Markov transitionrule MrkvArray.  Markov states can differ in their interest
    factor, permanent growth factor, and income distribution, so the inputs Rfree,
    PermGroFac, and IncShkDstn are arrays or lists specifying those values in each
    (succeeding) Markov state.

    Parameters
    ----------
    solution_next : ConsumerSolution
        The solution to next period's one period problem.
    IncShkDstn_list : [distribution.Distribution]
        A length N list of income distributions in each succeeding Markov
        state.  Each income distribution is
        a discrete approximation to the income process at the
        beginning of the succeeding period.
    LivPrb : float
        Survival probability; likelihood of being alive at the beginning of
        the succeeding period.
    DiscFac : float
        Intertemporal discount factor for future utility.
    CRRA : float
        Coefficient of relative risk aversion.
    Rfree_list : np.array
        Risk free interest factor on end-of-period assets for each Markov
        state in the succeeding period.
    PermGroGac_list : float
        Expected permanent income growth factor at the end of this period
        for each Markov state in the succeeding period.
    MrkvArray : numpy.array
        An NxN array representing a Markov transition matrix between discrete
        states.  The i,j-th element of MrkvArray is the probability of
        moving from state i in period t to state j in period t+1.
    BoroCnstArt: float or None
        Borrowing constraint for the minimum allowable assets to end the
        period with.  If it is less than the natural borrowing constraint,
        then it is irrelevant; BoroCnstArt=None indicates no artificial bor-
        rowing constraint.
    aXtraGrid: np.array
        Array of "extra" end-of-period asset values-- assets above the
        absolute minimum acceptable level.
    vFuncBool: boolean
        An indicator for whether the value function should be computed and
        included in the reported solution.
    CubicBool: boolean
        An indicator for whether the solver should use cubic or linear inter-
        polation.

    Returns
    -------
    solution : ConsumerSolution
        The solution to the single period consumption-saving problem. Includes
        a consumption function cFunc (using cubic or linear splines), a marg-
        inal value function vPfunc, a minimum acceptable level of normalized
        market resources mNrmMin, normalized human wealth hNrm, and bounding
        MPCs MPCmin and MPCmax.  It might also have a value function vFunc
        and marginal marginal value function vPPfunc.  All of these attributes
        are lists or arrays, with elements corresponding to the current
        Markov state.  E.g. solution.cFunc[0] is the consumption function
        when in the i=0 Markov state this period.
    """
    solver = ConsMarkovSolver(
        solution_next,
        IncShkDstn,
        LivPrb,
        DiscFac,
        CRRA,
        Rfree,
        PermGroFac,
        MrkvArray,
        BoroCnstArt,
        aXtraGrid,
        vFuncBool,
        CubicBool,
    )
    solution_now = solver.solve()
    return solution_now


####################################################################################################
####################################################################################################


class MarkovConsumerType(IndShockConsumerType):
    """
    An agent in the Markov consumption-saving model.  His problem is defined by a sequence
    of income distributions, survival probabilities, discount factors, and permanent
    income growth rates, as well as time invariant values for risk aversion, the
    interest rate, the grid of end-of-period assets, and how he is borrowing constrained.
    """

    time_vary_ = IndShockConsumerType.time_vary_ + ["MrkvArray"]

    # Is "Mrkv" a shock or a state?
    shock_vars_ = IndShockConsumerType.shock_vars_ + ["Mrkv"]
    state_vars = IndShockConsumerType.state_vars + ["Mrkv"]

    def __init__(self, **kwds):
        # HARK 0.17.0: Disable automatic construction, build manually
        IndShockConsumerType.__init__(self, construct=False, **kwds)

        # HARK 0.17 keeps Rfree TIME-VARYING for this type (the convention the
        # finite-horizon Jacobian agents in HA-Fiscal-HANK-SAM already use:
        # params["Rfree"] = T_cycle * [per-state array]). Callers must supply
        # Rfree as a time-vary list of per-state arrays — a BARE per-state
        # array gets sliced per-PERIOD into scalars and def_boundary's [j]
        # indexing fails (Step-4 migration chain, 2026-08-03; the SS dicts in
        # HA-Fiscal-HANK-SAM were fixed to wrap: Rfree=[np.ones(states)*R]).

        # HARK 0.17 migration completion (2026-08-03, corrected same day):
        # 0.17's AgentType no longer builds this type's terminal solution
        # (<=0.14 did it at construction). Build it HERE — at construction,
        # NOT in pre_solve: HA-Fiscal-HANK-SAM overwrites solution_terminal
        # on its finite-horizon Jacobian agents with the converged SS
        # solution (fake-news requirement), and a per-solve rebuild clobbers
        # that override (measured: sign-flipped 1e5-scale asset Jacobians).
        self.update_solution_terminal()

        from HARK.utilities import make_assets_grid
        from HARK.ConsumptionSaving.ConsIndShockModel import (
            make_lognormal_kNrm_init_dstn,
            make_lognormal_pLvl_init_dstn,
        )
        from HARK.Calibration.Income.IncomeProcesses import (
            construct_lognormal_income_process_unemployment,
            get_PermShkDstn_from_IncShkDstn,
            get_TranShkDstn_from_IncShkDstn,
        )
        
        self.aXtraGrid = make_assets_grid(
            aXtraMin=self.aXtraMin, aXtraMax=self.aXtraMax, aXtraCount=self.aXtraCount,
            aXtraExtra=self.aXtraExtra if hasattr(self, 'aXtraExtra') else None,
            aXtraNestFac=self.aXtraNestFac if hasattr(self, 'aXtraNestFac') else 3,
        )
        self.kNrmInitDstn = make_lognormal_kNrm_init_dstn(
            kLogInitMean=self.kLogInitMean, kLogInitStd=self.kLogInitStd,
            kNrmInitCount=getattr(self, 'kNrmInitCount', 15), RNG=self.RNG,
        )
        self.pLvlInitDstn = make_lognormal_pLvl_init_dstn(
            pLogInitMean=self.pLogInitMean, pLogInitStd=self.pLogInitStd,
            pLvlInitCount=getattr(self, 'pLvlInitCount', 15), RNG=self.RNG,
        )
        IncShkDstn = construct_lognormal_income_process_unemployment(
            T_cycle=self.T_cycle, PermShkStd=self.PermShkStd, PermShkCount=self.PermShkCount,
            TranShkStd=self.TranShkStd, TranShkCount=self.TranShkCount, T_retire=0,
            UnempPrb=self.UnempPrb, IncUnemp=self.IncUnemp,
            UnempPrbRet=None, IncUnempRet=None, RNG=self.RNG,
        )
        self.IncShkDstn = IncShkDstn
        self.PermShkDstn = get_PermShkDstn_from_IncShkDstn(IncShkDstn, self.RNG)
        self.TranShkDstn = get_TranShkDstn_from_IncShkDstn(IncShkDstn, self.RNG)
        self.solve_one_period = _solve_ConsMarkov

        if not hasattr(self, "global_markov"):
            self.global_markov = False

    def check_markov_inputs(self):
        """
        Many parameters used by MarkovConsumerType are arrays.  Make sure those arrays are the
        right shape.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        StateCount = self.MrkvArray[0].shape[0]

        # Check that arrays are the right shape
        if not isinstance(self.Rfree, np.ndarray) or self.Rfree.shape != (StateCount,):
            raise ValueError(
                "Rfree not the right shape, it should an array of Rfree of all the states."
            )

        # Check that arrays in lists are the right shape
        for MrkvArray_t in self.MrkvArray:
            if not isinstance(MrkvArray_t, np.ndarray) or MrkvArray_t.shape != (
                StateCount,
                StateCount,
            ):
                raise ValueError(
                    "MrkvArray not the right shape, it should be of the size states*statres."
                )
        for LivPrb_t in self.LivPrb:
            if not isinstance(LivPrb_t, np.ndarray) or LivPrb_t.shape != (StateCount,):
                raise ValueError(
                    "Array in LivPrb is not the right shape, it should be an array of length equal to number of states"
                )
        for PermGroFac_t in self.PermGroFac:
            if not isinstance(PermGroFac_t, np.ndarray) or PermGroFac_t.shape != (
                StateCount,
            ):
                raise ValueError(
                    "Array in PermGroFac is not the right shape, it should be an array of length equal to number of states"
                )

        # Now check the income distribution.
        # Note IncShkDstn is (potentially) time-varying, so it is in time_vary.
        # Therefore it is a list, and each element of that list responds to the income distribution
        # at a particular point in time.  Each income distribution at a point in time should itself
        # be a list, with each element corresponding to the income distribution
        # conditional on a particular Markov state.
        # TODO: should this be a numpy array too?
        for IncShkDstn_t in self.IncShkDstn:
            if not isinstance(IncShkDstn_t, list):
                raise ValueError(
                    "self.IncShkDstn is time varying and so must be a list"
                    + "of lists of Distributions, one per Markov State. Found "
                    + f"{self.IncShkDstn} instead"
                )
            elif len(IncShkDstn_t) != StateCount:
                raise ValueError(
                    "List in IncShkDstn is not the right length, it should be length equal to number of states"
                )

    def pre_solve(self):
        """
        Check to make sure that the inputs that are specific to MarkovConsumerType
        are of the right shape (if arrays) or length (if lists).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        # AgentType.pre_solve(self)
        # HAFISCAL_CHECK_MARKOV_INPUTS=1 (earnings-phase bring-up, 2026-08-28): re-enable HARK's
        # per-state shape asserts (Rfree/LivPrb/PermGroFac/MrkvArray/IncShkDstn all sized to
        # MrkvArray[0].shape[0]). Off by default because the estimation surface deliberately carries
        # per-state arrays LONGER than its base chain (first-StateCount sliced by the solver).
        if os.environ.get("HAFISCAL_CHECK_MARKOV_INPUTS", "").strip().lower() in ("1", "on", "true", "yes"):
            self.check_markov_inputs()
        # BUG-107: seed the terminal human wealth with its fixed point before an INFINITE-HORIZON
        # solve. This is the one hook that sees the IncShkDstn actually in force -- callers install
        # the distribution (and each Jacobian perturbation arm) AFTER construction, so a
        # construction-time seed would be the wrong arm's h, and compute_steady_state() is not the
        # only entry point (a bare .solve() is legitimate). It sets ONE field of an existing terminal
        # and is a no-op unless cycles == 0, so it cannot disturb what the note below protects: the
        # finite-horizon Jacobian agents (cycles == 1) whose terminal is hand-installed from the
        # converged steady state -- they inherit the fix through that solution instead.
        self.seed_terminal_human_wealth()
        # NOTE (2026-08-03): update_solution_terminal must NOT be called here.
        # A first fix put it in pre_solve ("idempotent"), which runs at every
        # solve() — and CLOBBERED the converged-SS terminal that
        # HA-Fiscal-HANK-SAM hand-installs on its finite-horizon Jacobian
        # agents (the fake-news method requires period-T policies = SS
        # policies). The result was sign-flipped, 1e5-scale asset Jacobians —
        # caught only by numerical comparison against the committed 2025-11
        # object. The <=0.14 semantics build the terminal at CONSTRUCTION,
        # leaving post-construction overrides intact; see __init__.

    def update_solution_terminal(self):
        """
        Update the terminal period solution.  This method should be run when a
        new AgentType is created or when CRRA changes.

        Parameters
        ----------
        none

        Returns
        -------
        none
        """
        # HARK 0.17.0: update_solution_terminal removed; use make_basic_CRRA_solution_terminal
        self.solution_terminal = make_basic_CRRA_solution_terminal(self.CRRA)

        # Make replicated terminal period solution: consume all resources, no human wealth, minimum m is 0
        StateCount = self.MrkvArray[0].shape[0]
        # HARK 0.17: the <=0.14 class attribute cFunc_terminal_ is gone; the
        # basic terminal's own cFunc IS the c=m terminal policy. Capture it
        # BEFORE the per-state listification overwrites the attribute.
        _cFunc_term = self.solution_terminal.cFunc
        self.solution_terminal.cFunc = StateCount * [_cFunc_term]
        self.solution_terminal.vFunc = StateCount * [self.solution_terminal.vFunc]
        self.solution_terminal.vPfunc = StateCount * [self.solution_terminal.vPfunc]
        self.solution_terminal.vPPfunc = StateCount * [self.solution_terminal.vPPfunc]
        self.solution_terminal.mNrmMin = np.zeros(StateCount)
        self.solution_terminal.hRto = np.zeros(StateCount)
        self.solution_terminal.MPCmax = np.ones(StateCount)
        self.solution_terminal.MPCmin = np.ones(StateCount)

    def seed_terminal_human_wealth(self, StateCount=None):
        """BUG-107: start the infinite-horizon backward iteration from the human-wealth FIXED POINT.

        `h` is the present value of future labour income discounted at `R`. It contains no discount
        factor, so two households with the same income process and the same `R` have the same `h`
        whatever their `beta`. The solver computes it by a recursion that runs alongside the policy
        iteration (`ConsMarkovSolver.calc_...`: h_t = M.(Gamma/R).(E_inc + h_{t+1})) and inherits the
        policy's stopping rule. That recursion is a partial sum whose ratio is rho(M.Gamma/R) ~ 1/R
        ~ 0.995 per iteration, while an IMPATIENT household's POLICY converges in ~50: the solver
        stops with a fraction of the sum accumulated, and `h` comes out beta-dependent by up to 84 %
        (BUG-107's table). It is used only as the interpolant's `intercept_limit = MPCmin*hNrm` --
        the perfect-foresight line the consumption function is extrapolated toward above the top
        gridpoint -- so the error is silent, and lands on exactly the atoms whose extrapolation a
        coarser grid would start to use.

        The recursion is EXACT given its terminal value; the only defect is the seed, which is zero.
        Seeding the fixed point h* = (I - D)^-1 D E_inc, D = M.diag(Gamma/R), makes every subsequent
        iterate exactly h* when the parameters are time-invariant (h* is by definition the recursion's
        fixed point), and leaves a genuinely dated chain -- the SSJ zeroth-column agent's perturbed
        income path -- free to move away from it period by period, which a direct fixed-point
        substitution in the solver would have destroyed.

        h* comes from `mom_bounds.solve_markov_human_wealth`, the SAME single source of truth
        `AggFiscalModel.compute_pf_decay_limits` calls for the PE model's terminal (owner ruling
        2026-08-30: "everything that CAN be reused must BE reused"). `mom_bounds` depends on numpy
        alone, so this is a plain import with no cycle through AggFiscalModel.

        INFINITE HORIZON ONLY (`cycles == 0`). In a true life-cycle problem the terminal period's
        human wealth really is zero and the truncated sum is the right answer; the SSJ finite chains
        are unaffected either way because their terminal is hand-installed from the converged
        steady-state solution after construction (see the 2026-08-03 note in `pre_solve`), which
        inherits this fix through `agent_SS`.

        Falls back to the existing zero seed, with a warning, whenever the fixed point is not
        available or not trustworthy (FHWC guard -> NaN, missing IncShkDstn, shape mismatch): the
        same guard discipline as the PE terminal's RIC/FHWC fallback.
        """
        if int(getattr(self, "cycles", 1)) != 0:
            return
        if StateCount is None:
            StateCount = self.MrkvArray[0].shape[0]
        try:
            from mom_bounds import solve_markov_human_wealth
            inc0 = self.IncShkDstn[0]
            if len(inc0) < StateCount:
                raise ValueError(f"IncShkDstn has {len(inc0)} states, need {StateCount}")
            E_inc = np.array([
                float(np.sum(np.asarray(inc0[j].pmv)
                             * np.asarray(inc0[j].atoms[0])
                             * np.asarray(inc0[j].atoms[1])))
                for j in range(StateCount)])
            R = np.asarray(self.Rfree[0], float).flatten()
            G = np.asarray(self.PermGroFac[0], float).flatten()
            R = np.full(StateCount, R[0]) if R.size == 1 else R[:StateCount]
            G = np.full(StateCount, G[0]) if G.size == 1 else G[:StateCount]
            hstar = solve_markov_human_wealth(
                np.asarray(self.MrkvArray[-1], float)[:StateCount, :StateCount],
                R, E_inc, PermGroFac_by_state=G)
            if hstar is None or not np.all(np.isfinite(hstar)):
                raise ValueError("human-wealth fixed point not finite (FHWC guard)")
        except AttributeError:
            return                       # IncShkDstn not installed yet (construction); nothing to do
        except Exception as e:                                  # noqa: BLE001 - documented fallback
            warnings.warn(
                f"BUG-107 terminal human-wealth seed unavailable ({e}); falling back to the zero "
                "seed, i.e. the under-converged partial sum. cFunc extrapolation above the solve "
                "grid top uses an intercept that is too small.")
            return
        self.solution_terminal.hNrm = np.asarray(hstar, float)
        self.hNrm_terminal_seed = np.asarray(hstar, float)

    def initialize_sim(self):
        self.shocks["Mrkv"] = np.zeros(self.AgentCount, dtype=int)
        IndShockConsumerType.initialize_sim(self)
        if (
            self.global_markov
        ):  # Need to initialize markov state to be the same for all agents
            base_draw = Uniform(seed=self.RNG.integers(0, 2**31 - 1)).draw(1)
            Cutoffs = np.cumsum(np.array(self.MrkvPrbsInit))
            self.shocks["Mrkv"] = np.ones(self.AgentCount) * np.searchsorted(
                Cutoffs, base_draw
            ).astype(int)
        self.shocks["Mrkv"] = self.shocks["Mrkv"].astype(int)

    def reset_rng(self):
        """
        Extended method that ensures random shocks are drawn from the same sequence
        on each simulation, which is important for structural estimation.  This
        method is called automatically by initialize_sim().

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        PerfForesightConsumerType.reset_rng(self)

        # Reset IncShkDstn if it exists (it might not because reset_rng is called at init)
        # HARK 0.17.0 compatibility: Handle both IndexDistribution and list-of-lists
        if hasattr(self, "IncShkDstn"):
            if hasattr(self.IncShkDstn, '__len__'):
                # Standard list-of-lists format
                T = len(self.IncShkDstn)
                for t in range(T):
                    for dstn in self.IncShkDstn[t]:
                        dstn.reset()
            elif hasattr(self.IncShkDstn, 'reset'):
                # IndexDistribution format (HARK 0.17.0)
                self.IncShkDstn.reset()

    def sim_death(self):
        """
        Determines which agents die this period and must be replaced.  Uses the sequence in LivPrb
        to determine survival probabilities for each agent.

        Parameters
        ----------
        None

        Returns
        -------
        which_agents : np.array(bool)
            Boolean array of size AgentCount indicating which agents die.
        """
        # Determine who dies
        LivPrb = np.array(self.LivPrb)[
            self.t_cycle - 1, self.shocks["Mrkv"]
        ]  # Time has already advanced, so look back one
        DiePrb = 1.0 - LivPrb
        DeathShks = Uniform(seed=self.RNG.integers(0, 2**31 - 1)).draw(
            N=self.AgentCount
        )
        which_agents = DeathShks < DiePrb
        if self.T_age is not None:  # Kill agents that have lived for too many periods
            too_old = self.t_age >= self.T_age
            which_agents = np.logical_or(which_agents, too_old)
        return which_agents

    def sim_birth(self, which_agents):
        """
        Makes new Markov consumer by drawing initial normalized assets, permanent income levels, and
        discrete states. 
        
        HARK 0.17.0 COMPATIBILITY: Override IndShockConsumerType.sim_birth to replicate
        HARK 0.14.1's RNG consumption pattern. HARK 0.14.1 creates new Lognormal distributions
        with RNG.integers() seeds, while HARK 0.17.0 uses pre-built distributions.

        Parameters
        ----------
        which_agents : np.array(Bool)
            Boolean array of size self.AgentCount indicating which agents should be "born".

        Returns
        -------
        None
        """
        from HARK.distributions import Lognormal
        
        N = np.sum(which_agents)  # Number of new consumers to make
        
        # HARK 0.14.1 style: Create new Lognormal distributions with explicit seeds
        # This consumes RNG integers in the same order as 0.14.1
        # Check both 0.14.1 naming (aNrmInitMean) and 0.17.0 naming (kLogInitMean)
        aNrmInitMean = getattr(self, 'aNrmInitMean', getattr(self, 'kLogInitMean', 0.0))
        aNrmInitStd = getattr(self, 'aNrmInitStd', getattr(self, 'kLogInitStd', 1.0))
        self.state_now["aNrm"][which_agents] = Lognormal(
            mu=aNrmInitMean,
            sigma=aNrmInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        pLvlInitMean = getattr(self, 'pLvlInitMean', getattr(self, 'pLogInitMean', 0.0))
        pLvlInitStd = getattr(self, 'pLvlInitStd', getattr(self, 'pLogInitStd', 0.0))
        pLvlInitMeanNow = pLvlInitMean + np.log(self.state_now["PlvlAgg"])
        self.state_now["pLvl"][which_agents] = Lognormal(
            pLvlInitMeanNow,
            pLvlInitStd,
            seed=self.RNG.integers(0, 2**31 - 1),
        ).draw(N)
        
        self.t_age[which_agents] = 0
        if not hasattr(self, "PerfMITShk"):
            self.PerfMITShk = False
        if not self.PerfMITShk:
            self.t_cycle[which_agents] = 0
        
        # Draw initial Markov distribution
        if (
            not self.global_markov
        ):  # Markov state is not changed if it is set at the global level
            base_draws = Uniform(seed=self.RNG.integers(0, 2**31 - 1)).draw(N)
            Cutoffs = np.cumsum(np.array(self.MrkvPrbsInit))
            self.shocks["Mrkv"][which_agents] = np.searchsorted(
                Cutoffs, base_draws
            ).astype(int)

    def get_markov_states(self):
        """
        Draw new Markov states for each agent in the simulated population, using
        the attribute MrkvArray to determine transition probabilities.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        dont_change = (
            self.t_age == 0
        )  # Don't change Markov state for those who were just born (unless global_markov)
        if self.t_sim == 0:  # Respect initial distribution of Markov states
            dont_change[:] = True

        # Determine which agents are in which states right now
        J = self.MrkvArray[0].shape[0]
        MrkvPrev = self.shocks["Mrkv"]
        MrkvNow = np.zeros(self.AgentCount, dtype=int)

        # Draw new Markov states for each agent
        for t in range(self.T_cycle):
            markov_process = MarkovProcess(
                self.MrkvArray[t], seed=self.RNG.integers(0, 2**31 - 1)
            )
            right_age = self.t_cycle == t
            MrkvNow[right_age] = markov_process.draw(MrkvPrev[right_age])
        if not self.global_markov:
            MrkvNow[dont_change] = MrkvPrev[dont_change]

        self.shocks["Mrkv"] = MrkvNow.astype(int)

    def get_shocks(self):
        """
        Gets new Markov states and permanent and transitory income shocks for this period.  Samples
        from IncShkDstn for each period-state in the cycle.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.get_markov_states()
        MrkvNow = self.shocks["Mrkv"]

        # Now get income shocks for each consumer, by cycle-time and discrete state
        PermShkNow = np.zeros(self.AgentCount)  # Initialize shock arrays
        TranShkNow = np.zeros(self.AgentCount)
        for t in range(self.T_cycle):
            for j in range(self.MrkvArray[t].shape[0]):
                these = np.logical_and(t == self.t_cycle, j == MrkvNow)
                N = np.sum(these)
                if N > 0:
                    IncShkDstnNow = self.IncShkDstn[t - 1][
                        j
                    ]  # set current income distribution
                    PermGroFacNow = self.PermGroFac[t - 1][
                        j
                    ]  # and permanent growth factor

                    # Get random draws of income shocks from the discrete distribution
                    EventDraws = IncShkDstnNow.draw_events(N)
                    PermShkNow[these] = (
                        IncShkDstnNow.atoms[0][EventDraws] * PermGroFacNow
                    )  # permanent "shock" includes expected growth
                    TranShkNow[these] = IncShkDstnNow.atoms[1][EventDraws]
        newborn = self.t_age == 0
        PermShkNow[newborn] = 1.0
        TranShkNow[newborn] = 1.0
        self.shocks["PermShk"] = PermShkNow
        self.shocks["TranShk"] = TranShkNow

    def read_shocks_from_history(self):
        """
        A slight modification of AgentType.read_shocks that makes sure that MrkvNow is int, not float.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        IndShockConsumerType.read_shocks_from_history(self)
        self.shocks["Mrkv"] = self.shocks["Mrkv"].astype(int)

    def get_Rfree(self):
        """
        Returns an array of size self.AgentCount with interest factor that varies with discrete state.

        Parameters
        ----------
        None

        Returns
        -------
        RfreeNow : np.array
             Array of size self.AgentCount with risk free interest rate for each agent.
        """
        RfreeNow = self.Rfree[self.shocks["Mrkv"]]
        return RfreeNow

    def get_controls(self):
        """
        Calculates consumption for each consumer of this type using the consumption functions.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        cNrmNow = np.zeros(self.AgentCount) + np.nan
        MPCnow = np.zeros(self.AgentCount) + np.nan
        J = self.MrkvArray[0].shape[0]

        MrkvBoolArray = np.zeros((J, self.AgentCount), dtype=bool)
        for j in range(J):
            MrkvBoolArray[j, :] = j == self.shocks["Mrkv"]

        for t in range(self.T_cycle):
            right_t = t == self.t_cycle
            for j in range(J):
                these = np.logical_and(right_t, MrkvBoolArray[j, :])
                cNrmNow[these], MPCnow[these] = (
                    self.solution[t]
                    .cFunc[j]
                    .eval_with_derivative(self.state_now["mNrm"][these])
                )
        self.controls["cNrm"] = cNrmNow
        self.MPCnow = MPCnow

    def calc_bounding_values(self):
        """
        Calculate human wealth plus minimum and maximum MPC in an infinite
        horizon model with only one period repeated indefinitely.  Store results
        as attributes of self.  Human wealth is the present discounted value of
        expected future income after receiving income this period, ignoring mort-
        ality.  The maximum MPC is the limit of the MPC as m --> mNrmMin.  The
        minimum MPC is the limit of the MPC as m --> infty.  Results are all
        np.array with elements corresponding to each Markov state.

        NOT YET IMPLEMENTED FOR THIS CLASS

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        raise NotImplementedError()

    def make_euler_error_func(self, mMax=100, approx_inc_dstn=True):
        """
        Creates a "normalized Euler error" function for this instance, mapping
        from market resources to "consumption error per dollar of consumption."
        Stores result in attribute eulerErrorFunc as an interpolated function.
        Has option to use approximate income distribution stored in self.IncShkDstn
        or to use a (temporary) very dense approximation.

        NOT YET IMPLEMENTED FOR THIS CLASS

        Parameters
        ----------
        mMax : float
            Maximum normalized market resources for the Euler error function.
        approx_inc_dstn : Boolean
            Indicator for whether to use the approximate discrete income distri-
            bution stored in self.IncShkDstn[0], or to use a very accurate
            discrete approximation instead.  When True, uses approximation in
            IncShkDstn; when False, makes and uses a very dense approximation.

        Returns
        -------
        None

        Notes
        -----
        This method is not used by any other code in the library. Rather, it is here
        for expository and benchmarking purposes.
        """
        raise NotImplementedError()
    
    # HARK 0.17: define_distribution_grid moved from the core agent types to
    # ConsNewKeynesianModel (the sequence-space toolkit's home). Borrow it
    # unbound — it is generic (writes self.dist_mGrid/dist_pGrid from standard
    # parameters), and the Markov-aware consumers below read exactly those.
    # Step-4 migration chain, 2026-08-03.
    #
    # ALSO borrow its private helper (2026-08-19). The 2026-08-13 HARK re-pin
    # (bfb77471) refactored define_distribution_grid to delegate the mGrid
    # assignment to a NEW private method `_assign_dist_mGrid`; borrowing only
    # the public method then dies with AttributeError at the first
    # compute_steady_state — which is exactly how the cold-rerun chain's first
    # S4 execution on this pin failed (2026-08-19; Step 4 had not run since
    # the re-pin, so the board's GREEN never exercised this path). Borrowing a
    # method unbound means adopting its private callees as part of the deal;
    # the guard test test_step4_nk_borrow.py enumerates them from the HARK
    # source at test time so the NEXT refactor is caught by CI, not by a
    # 10-minute-in battery crash.
    define_distribution_grid = _NKConsumerType.define_distribution_grid
    _assign_dist_mGrid = _NKConsumerType._assign_dist_mGrid

    def harmenberg_income_process(self):
        self.state_num = len(self.MrkvArray[0])
        self.dist_pGrid = np.array([1])
        if self.neutral_measure == True:
            for m in range(self.state_num):
                self.IncShkDstn[0][m].pmv = self.IncShkDstn[0][m].pmv * self.IncShkDstn[0][m].atoms[0]

    def calc_transition_matrix(self, shk_dstn = None): 

        if self.cycles == 0: 
            if shk_dstn == None:
                shk_dstn = self.IncShkDstn[0]
        
            dist_mGrid =  self.dist_mGrid
            dist_pGrid = self.dist_pGrid
            
            n_p = len(dist_pGrid) # number of permanent shock points
            n_m = len(self.MrkvArray[0]) # number of Markov states
            n_a = self.dist_mGrid.size # number of cash on hand gridpoints

            self.cPol_Grid = np.zeros((n_m, n_a))
            self.aPol_Grid = np.zeros((n_m, n_a))
                
            self.tran_matrix = np.zeros((n_m, n_a, n_m, n_a))
            
            # HARK 0.17: self.Rfree is a time-vary list of PER-STATE arrays;
            # [0] unwraps the period, [m] below picks THIS state's rate
            # (the old first-state-scalar read only worked because all
            # states share R). Step-4 migration chain, 2026-08-03.
            Rfree = self.Rfree[0]
            bNext = np.zeros((n_m, n_a))
            # BUG-097 (2026-08-28): the growth factor of the state transitioned
            # INTO, Gamma = PermGroFac[0][mp] (ones under
            # HAFISCAL_STEP4_TRANMAT_GROWTH=0), so the transition evolves
            # m' = R*a/(Gamma*psi) + theta exactly as the solve does
            # (ConsMarkovSolver conditions on the NEXT state j with
            # PermGroFac_list[j]). Applied per (m, mp) pair below; x/1.0 == x,
            # so with Gamma == 1 the build is bitwise the pre-BUG-097 one.
            Gro_next = _tranmat_mod().permgrofac_next(self, 0, n_m)
            # earnings phase (2026-08-29): newborns of a matured destination are born growing
            # (see _place_tran_block_1D / step4_fast_tranmat.newborn_phase_J); 0 = no phase
            J_phase = _tranmat_mod().newborn_phase_J(self, n_m)

            shk_prbs =  np.zeros((n_m, self.TranShkCount * self.PermShkCount))
            tran_shks = np.zeros((n_m, self.TranShkCount * self.PermShkCount))
            perm_shks = np.zeros((n_m, self.TranShkCount * self.PermShkCount))

            # produce C and A grids
            for m in range(n_m):
                self.cPol_Grid[m] = self.solution[0].cFunc[m](dist_mGrid)
                self.aPol_Grid[m] = dist_mGrid - self.cPol_Grid[m]

                bNext[m] = Rfree[m] * self.aPol_Grid[m]
                shk_prbs[m] = shk_dstn[m].pmv
                tran_shks[m] = shk_dstn[m].atoms[1]
                perm_shks[m] = shk_dstn[m].atoms[0]

            LivPrb = self.LivPrb[0][0] # Update probability of staying alive this period
            # BUG-108: the p-weighted SURVIVOR WEIGHT per destination state, from the SST. Under the
            # neutral measure with mortality AND growth the surviving mass carries LivPrb*Gamma, not
            # LivPrb; the newborn complement follows from it inside the builders. Gamma == 1 (the
            # growth-free transition, and the frozen monolith) returns LivPrb exactly, so that build
            # stays byte-identical.
            w_surv = _pweighted_survival().survivor_weight(LivPrb, Gro_next)

            tran_matrix_ss = None
            mrkv_array = self.MrkvArray[0]

            if len(dist_pGrid) == 1:
                tran_mat = np.zeros((n_m, n_a, n_m, n_a))
                #
                for m in range(n_m):
                    for mp in range(n_m):
                        if  mrkv_array[m, mp] > 0:
                            _place_tran_block_1D(tran_mat, m, mp, mrkv_array[m, mp], dist_mGrid,
                                                 bNext[m] / Gro_next[mp], shk_prbs, perm_shks,
                                                 tran_shks, w_surv[mp], J_phase)

                self.tran_matrix = tran_mat.reshape(n_m * n_a, n_m * n_a)

            else:
                if J_phase > 0:
                    raise NotImplementedError(
                        "earnings phase: the 2D (m, p) transition builder has no newborn phase reset; "
                        "Step 4 runs on the Harmenberg neutral measure (dist_pGrid of length 1)")
                # for each markov state, n_a * n_p possible states
                tran_mat = np.zeros((n_m, n_a * n_p, n_m, n_a * n_p))

                for m in range(n_m):
                    for mp in range(n_m):   
                        if  mrkv_array[m, mp] > 0:  
                            # 2D (m,p) branch: unit newborns and (below) raw LivPrb are
                            # CORRECT BY DESIGN here (dual-path sweep 2026-09-02): this
                            # representation carries p explicitly, so the per-capita split is
                            # the right arithmetic (the LGamma survivor weight belongs to the
                            # p-WEIGHTED 1D measure), and IMPROVEMENT-002's newborn-income
                            # convention was deliberately scoped to the HANK 1D path only --
                            # flipping PE-facing newborns is re-estimation territory.
                            NewBornDist = jump_to_grid_2D(np.ones_like(tran_shks[mp]), 
                                                          np.ones_like(tran_shks[mp]), 
                                                          shk_prbs[mp], 
                                                          dist_mGrid, 
                                                          dist_pGrid)
                            t_mat = mrkv_array[m, mp] * gen_tran_matrix_2D(dist_mGrid,
                                                                           dist_pGrid,
                                                                           bNext[m] / Gro_next[mp],
                                                                           shk_prbs[mp],
                                                                           perm_shks[mp],
                                                                           tran_shks[mp],
                                                                           LivPrb,
                                                                           NewBornDist)
                            tran_mat[mp, :, m, :] = t_mat

                self.tran_matrix = tran_mat.reshape(n_m * n_a * n_p, n_m * n_a * n_p)

        elif self.cycles > 1:
            print('calc_transition_matrix requires cycles = 0 or cycles = 1')
        
        elif self.T_cycle!= 0:

            if shk_dstn == None:
                shk_dstn = self.IncShkDstn

            if _finite_tranmat_fast(self, shk_dstn):
                return

            dist_mGrid = self.dist_mGrid
            dist_pGrid = self.dist_pGrid

            n_p = len(dist_pGrid[0])
            n_m = len(self.MrkvArray[0]) # number of Markov states
            n_a = self.dist_mGrid.size # number of cash on hand gridpoints
            bigT = self.T_cycle

            self.cPol_Grid = np.zeros((bigT, n_m, n_a))
            self.aPol_Grid = np.zeros((bigT, n_m, n_a))

            self.tran_matrix = []
            # earnings phase: newborns of a matured destination are born growing (0 = no phase)
            J_phase = _tranmat_mod().newborn_phase_J(self, n_m)

            for t in range(bigT):
                if type(self.dist_pGrid) == list:
                    dist_pGrid = self.dist_pGrid[t] #Permanent income grid this period
                else:
                    dist_pGrid = self.dist_pGrid #If here then use prespecified permanent income grid

                Rfree = self.Rfree[t]  # per-state array; [m] below (see infinite-horizon note)
                # BUG-097: PermGroFac[t][mp], the state transitioned INTO (see the
                # infinite-horizon note); the kernel path gets the same array
                Gro_next = _tranmat_mod().permgrofac_next(self, t, n_m)

                bNext = np.zeros((n_m, n_a))
            
                shk_prbs =  np.zeros((n_m, self.TranShkCount * self.PermShkCount))
                tran_shks = np.zeros((n_m, self.TranShkCount * self.PermShkCount))
                perm_shks = np.zeros((n_m, self.TranShkCount * self.PermShkCount))

                # produce C and A grids
                for m in range(n_m):
                    self.cPol_Grid[t][m] = self.solution[t].cFunc[m](dist_mGrid)
                    self.aPol_Grid[t][m] = dist_mGrid - self.cPol_Grid[t][m]
                        
                    bNext[m] = Rfree[m] * self.aPol_Grid[t][m]
                    shk_prbs[m] = shk_dstn[t][m].pmv
                    tran_shks[m] = shk_dstn[t][m].atoms[1]
                    perm_shks[m] = shk_dstn[t][m].atoms[0]
    
                LivPrb = self.LivPrb[t][0] # Update probability of staying alive this period
                w_surv = _pweighted_survival().survivor_weight(LivPrb, Gro_next)   # BUG-108, per period
            
                if len(dist_pGrid) == 1:
                    mrkv_array = self.MrkvArray[t]
                    tran_mat = np.zeros((n_m, n_a, n_m, n_a))

                    for m in range(n_m):
                        for mp in range(n_m):
                            if  mrkv_array[m, mp] > 0:
                                _place_tran_block_1D(tran_mat, m, mp, mrkv_array[m, mp], dist_mGrid,
                                                     bNext[m] / Gro_next[mp], shk_prbs, perm_shks,
                                                     tran_shks, w_surv[mp], J_phase)

                    tran_mat = tran_mat.reshape(n_m * n_a, n_m * n_a)
                    self.tran_matrix.append(tran_mat)  # tran_mat is freshly allocated each t; the old deepcopy re-copied 4 MB x 300 per agent for nothing

                else:
                    if J_phase > 0:
                        raise NotImplementedError(
                            "earnings phase: the 2D (m, p) transition builder has no newborn phase reset; "
                            "Step 4 runs on the Harmenberg neutral measure (dist_pGrid of length 1)")
                    mrkv_array = self.MrkvArray[t]
                    tran_mat = np.zeros((n_m, n_a * n_p, n_m, n_a * n_p))

                    for m in range(n_m):
                        for mp in range(n_m):   
                            if  mrkv_array[m, mp] > 0:  
                                # Same 2D-branch design note as the infinite-horizon site
                                # above: explicit-p representation => per-capita split + unit
                                # newborns are correct; not a missed IMPROVEMENT-002 routing.
                                NewBornDist = jump_to_grid_2D(np.ones_like(tran_shks[mp]),
                                                              np.ones_like(tran_shks[mp]), 
                                                              shk_prbs[mp], 
                                                              dist_mGrid,
                                                              dist_pGrid)
                                t_mat = mrkv_array[m, mp] * gen_tran_matrix_2D(dist_mGrid,
                                                                               dist_pGrid,
                                                                               bNext[m] / Gro_next[mp],
                                                                               shk_prbs[mp],
                                                                               perm_shks[mp],
                                                                               tran_shks[mp],
                                                                               LivPrb,
                                                                               NewBornDist)
                                tran_mat[mp, :, m, :] = t_mat

                    tran_mat = tran_mat.reshape(n_m * n_a * n_p, n_m * n_a * n_p)
                    self.tran_matrix.append(tran_mat)  # tran_mat is freshly allocated each t; the old deepcopy re-copied 4 MB x 300 per agent for nothing 

    def compute_steady_state(self, harmenberg = True, num_pointsP = 25):
        # Compute steady state to perturb around
        self.cycles = 0
        self.solve()

        if(harmenberg):
            self.neutral_measure = True
            self.harmenberg_income_process()
            self.define_distribution_grid()
            self.calc_transition_matrix()
            self.calc_ergodic_dist()

            self.A_ss = np.dot(self.aPol_Grid.flatten(), self.vec_erg_dstn)[0]
            self.C_ss = np.dot(self.cPol_Grid.flatten(), self.vec_erg_dstn)[0]
        
        else:
            self.define_distribution_grid(num_pointsP = num_pointsP)
            self.calc_transition_matrix()
            self.calc_ergodic_dist()

            pGrid = self.dist_pGrid

            n_p = len(pGrid)
            n_m = len(self.MrkvArray[0])
            n_a = len(self.dist_mGrid)

            self.gridc = np.zeros((n_m, n_a, n_p))
            self.grida = np.zeros((n_m, n_a, n_p))

            for m in range(n_m):
                for j in range(n_p):
                    self.gridc[m, :, j] = pGrid[j] * self.cPol_Grid[m]  # unnormalized Consumption policy grid
                    self.grida[m, :, j] = pGrid[j] * self.aPol_Grid[m]  # unnormalized Asset policy grid

            self.C_ss = np.dot(self.gridc.flatten(), self.vec_erg_dstn)[0]  # Aggregate Consumption
            self.A_ss = np.dot(self.grida.flatten(), self.vec_erg_dstn)[0]  # Aggregate Assets
        
        return self.A_ss, self.C_ss
    
    def calc_ergodic_dist(self, transition_matrix=None):
        """
        Calculates the ergodic distribution across normalized market resources and
        permanent income as the eigenvector associated with the eigenvalue 1.
        The distribution is stored as attributes of self both as a vector and as a reshaped array with the ij'th element representing
        the probability of being at the i'th point on the mGrid and the j'th
        point on the pGrid.

        Parameters
        ----------
        transition_matrix: List
                    list with one transition matrix whose ergordic distribution is to be solved
        Returns
        -------
        None
        """

        if not isinstance(transition_matrix, list):
            transition_matrix = [self.tran_matrix]

        eigen, ergodic_distr = sp.linalg.eigs(
            transition_matrix[0], v0 = np.ones(len(transition_matrix[0])), k = 1, which = "LM"
        )  # Solve for ergodic distribution

        ergodic_distr = ergodic_distr.real / np.sum(ergodic_distr.real)
        self.vec_erg_dstn = ergodic_distr
