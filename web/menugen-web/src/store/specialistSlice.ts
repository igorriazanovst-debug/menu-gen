import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import api from "../api/client";

// ── Types ────────────────────────────────────────────────────────────────────

export interface SpecialistProfile {
  id: number;
  name: string;
  email: string;
  specialist_type: "dietitian" | "trainer";
  is_verified: boolean;
  verified_at: string | null;
}

export interface FamilyMemberShort {
  id: number;
  name: string;
  email: string;
  role: string;
}

export interface ClientFamily {
  id: number;
  name: string;
  members: FamilyMemberShort[];
  assignment_id: number | null;
  assignment_status: string | null;
}

export interface Recommendation {
  id: number;
  rec_type: "supplement" | "food" | "exercise" | "other";
  name: string;
  dosage: string;
  frequency: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  is_read: boolean;
  member_name: string | null;
  created_at: string;
}

export interface RecommendationWrite {
  rec_type: string;
  name: string;
  dosage?: string;
  frequency?: string;
  start_date?: string;
  end_date?: string;
  member?: number;
}

export interface PendingAssignment {
  assignment_id: number;
  family_id: number;
  family_name: string;
}

export interface ClientMenu {
  id: number;
  start_date: string;
  end_date: string;
  period_days: number;
  status: string;
  generated_at: string;
}

interface SpecialistState {
  profile: SpecialistProfile | null;
  clients: ClientFamily[];
  pendingAssignments: PendingAssignment[];
  selectedClientMenus: ClientMenu[];
  selectedClientRecs: Recommendation[];
  loading: boolean;
  error: string | null;
}

const initialState: SpecialistState = {
  profile: null,
  clients: [],
  pendingAssignments: [],
  selectedClientMenus: [],
  selectedClientRecs: [],
  loading: false,
  error: null,
};

// ── Thunks ───────────────────────────────────────────────────────────────────

export const fetchSpecialistProfile = createAsyncThunk(
  "specialist/fetchProfile",
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get("/specialists/profile/");
      return res.data as SpecialistProfile;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const registerAsSpecialist = createAsyncThunk(
  "specialist/register",
  async (specialist_type: string, { rejectWithValue }) => {
    try {
      const res = await api.post("/specialists/register/", { specialist_type });
      return res.data as SpecialistProfile;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const fetchClients = createAsyncThunk(
  "specialist/fetchClients",
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get("/specialists/cabinet/clients/");
      return res.data as ClientFamily[];
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const fetchPendingAssignments = createAsyncThunk(
  "specialist/fetchPending",
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get("/specialists/cabinet/pending/");
      return res.data as PendingAssignment[];
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const acceptAssignment = createAsyncThunk(
  "specialist/acceptAssignment",
  async (assignmentId: number, { rejectWithValue }) => {
    try {
      await api.post(`/specialists/assignments/${assignmentId}/accept/`);
      return assignmentId;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const endAssignment = createAsyncThunk(
  "specialist/endAssignment",
  async (assignmentId: number, { rejectWithValue }) => {
    try {
      await api.post(`/specialists/assignments/${assignmentId}/end/`);
      return assignmentId;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const fetchClientMenus = createAsyncThunk(
  "specialist/fetchClientMenus",
  async (familyId: number, { rejectWithValue }) => {
    try {
      const res = await api.get(`/specialists/cabinet/clients/${familyId}/menus/`);
      return res.data as ClientMenu[];
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const fetchClientRecommendations = createAsyncThunk(
  "specialist/fetchClientRecs",
  async (familyId: number, { rejectWithValue }) => {
    try {
      const res = await api.get(`/specialists/cabinet/clients/${familyId}/recommendations/`);
      return res.data as Recommendation[];
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const createRecommendation = createAsyncThunk(
  "specialist/createRec",
  async (
    { familyId, data }: { familyId: number; data: RecommendationWrite },
    { rejectWithValue }
  ) => {
    try {
      const res = await api.post(
        `/specialists/cabinet/clients/${familyId}/recommendations/`,
        data
      );
      return res.data as Recommendation;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const deleteRecommendation = createAsyncThunk(
  "specialist/deleteRec",
  async (
    { familyId, recId }: { familyId: number; recId: number },
    { rejectWithValue }
  ) => {
    try {
      await api.delete(`/specialists/cabinet/clients/${familyId}/recommendations/${recId}/`);
      return recId;
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

export const swapMenuItemSpecialist = createAsyncThunk(
  "specialist/swapMenuItem",
  async (
    { familyId, menuId, itemId, recipeId }: { familyId: number; menuId: number; itemId: number; recipeId: number },
    { rejectWithValue }
  ) => {
    try {
      await api.patch(
        `/specialists/cabinet/clients/${familyId}/menus/${menuId}/items/${itemId}/`,
        { recipe_id: recipeId }
      );
    } catch (e: any) {
      return rejectWithValue(e.response?.data?.detail ?? "Ошибка");
    }
  }
);

// ── Slice ────────────────────────────────────────────────────────────────────

const specialistSlice = createSlice({
  name: "specialist",
  initialState,
  reducers: {
    clearSpecialistError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    const pending = (state: SpecialistState) => {
      state.loading = true;
      state.error = null;
    };
    const failed = (state: SpecialistState, action: any) => {
      state.loading = false;
      state.error = action.payload as string;
    };

    builder
      .addCase(fetchSpecialistProfile.pending, pending)
      .addCase(fetchSpecialistProfile.fulfilled, (state, action) => {
        state.loading = false;
        state.profile = action.payload;
      })
      .addCase(fetchSpecialistProfile.rejected, failed)

      .addCase(registerAsSpecialist.pending, pending)
      .addCase(registerAsSpecialist.fulfilled, (state, action) => {
        state.loading = false;
        state.profile = action.payload;
      })
      .addCase(registerAsSpecialist.rejected, failed)

      .addCase(fetchClients.pending, pending)
      .addCase(fetchClients.fulfilled, (state, action) => {
        state.loading = false;
        state.clients = action.payload;
      })
      .addCase(fetchClients.rejected, failed)

      .addCase(fetchPendingAssignments.fulfilled, (state, action) => {
        state.pendingAssignments = action.payload;
      })

      .addCase(acceptAssignment.fulfilled, (state, action) => {
        state.pendingAssignments = state.pendingAssignments.filter(
          (a) => a.assignment_id !== action.payload
        );
      })

      .addCase(fetchClientMenus.pending, pending)
      .addCase(fetchClientMenus.fulfilled, (state, action) => {
        state.loading = false;
        state.selectedClientMenus = action.payload;
      })
      .addCase(fetchClientMenus.rejected, failed)

      .addCase(fetchClientRecommendations.pending, pending)
      .addCase(fetchClientRecommendations.fulfilled, (state, action) => {
        state.loading = false;
        state.selectedClientRecs = action.payload;
      })
      .addCase(fetchClientRecommendations.rejected, failed)

      .addCase(createRecommendation.fulfilled, (state, action) => {
        state.selectedClientRecs.unshift(action.payload);
      })

      .addCase(deleteRecommendation.fulfilled, (state, action) => {
        state.selectedClientRecs = state.selectedClientRecs.map((r) =>
          r.id === action.payload ? { ...r, is_active: false } : r
        );
      });
  },
});

export const { clearSpecialistError } = specialistSlice.actions;
export default specialistSlice.reducer;
