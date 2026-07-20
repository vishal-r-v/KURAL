export type UrgencyType = 'Low' | 'Medium' | 'High';
export type CategoryType = 'Water' | 'Roads' | 'Electricity' | 'Sanitation' | 'Others';
export type StatusType = 'Filed' | 'Routed' | 'In Progress' | 'Escalated' | 'Resolved';

export interface TimelineEvent {
  status: StatusType;
  title: string;
  description: string;
  date: string;
  isCompleted: boolean;
  /** B2: true for simulated citizen-notification log entries (not a real state transition). */
  isNotification?: boolean;
}

export interface Complaint {
  id: string;
  /** Part B: citizen-facing structured ticket ID, e.g. 'GCC/SWM/2026/00147'.
   *  This is what citizens should see/quote — `id` is the internal UUID. */
  ticketId: string;
  title: string;
  description: string;
  location: string;
  ward: string;
  urgency: UrgencyType;
  /** B3: one-sentence Claude-generated rationale for the urgency classification. */
  urgencyReason?: string;
  category: CategoryType;
  status: StatusType;
  department: string;
  contact: string;
  officer?: string;
  createdAt: string;
  timeline: TimelineEvent[];
  /** B1: how many other citizens have reported this same issue (set on the original report). */
  duplicateCount?: number;
  /** B1: if this report was linked as a duplicate, the id of the original complaint. */
  duplicateOf?: string;
}
